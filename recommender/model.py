"""Train TF-IDF/NMF retrieval and a population profile from course completions."""
import hashlib
import json
import platform
from pathlib import Path

import joblib
import numpy as np
import sklearn
from sklearn.decomposition import NMF
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

from .catalog import Catalog, source_hashes
from .taxonomy import taxonomy_payload

MODEL_VERSION = "1.0"


def taxonomy_hash():
    return hashlib.sha256(json.dumps(taxonomy_payload(), sort_keys=True).encode()).hexdigest()


def normalize_text(text):
    # A few transparent aliases bridge common resume abbreviations to the catalog.
    import re
    for pattern, replacement in ((r"\bNLP\b", "natural language processing"),
                                  (r"\bLLMs?\b", "large language models"),
                                  (r"\bML\b", "machine learning"),
                                  (r"\bAI\b", "artificial intelligence"),
                                  (r"\bETL\b", "data engineering pipelines")):
        text = re.sub(pattern, replacement, text, flags=re.I)
    return text


class RecommendationModel:
    def fit(self, catalog: Catalog, n_topics=16):
        self.ids = sorted(cid for cid in catalog.courses if catalog.regular(cid))
        self.index = {cid: index for index, cid in enumerate(self.ids)}
        docs = [normalize_text(" ".join([catalog.courses[cid]["title"]] * 3 + [catalog.courses[cid]["description"]]))
                for cid in self.ids]
        self.vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True,
                                          max_df=0.98, min_df=1)
        self.course_vectors = self.vectorizer.fit_transform(docs)
        self.topic_model = NMF(n_components=min(n_topics, len(self.ids) - 1), init="nndsvda", random_state=42,
                               max_iter=1000, tol=0.0005)
        self.course_topics = normalize(self.topic_model.fit_transform(self.course_vectors))
        # Equal weight per student and per distinct completed regular course.
        # Credit amounts, GPA, grades, generated interests and resumes are not features.
        self.population = {}
        for sid in sorted(catalog.students):
            positions = [self.index[cid] for cid in sorted(catalog.completed(sid)) if cid in self.index]
            if positions:
                average = np.asarray(self.course_vectors[positions].mean(axis=0))
                self.population[sid] = normalize(average).ravel()
        terms = self.vectorizer.get_feature_names_out()
        self.report = {
            "model_version": MODEL_VERSION, "algorithm": "TF-IDF + nonnegative matrix factorization + population centroid",
            "random_seed": 42, "regular_courses": len(self.ids), "vocabulary_size": len(terms),
            "topics": self.topic_model.n_components_, "nmf_iterations": self.topic_model.n_iter_,
            "nmf_reconstruction_error": float(self.topic_model.reconstruction_err_),
            "population_students": len(self.population), "population_source": "provided_roster_course_completion_proxy",
            "population_is_stated_interest": False, "synthetic_samples_used_in_training": False,
            "credit_amounts_used": False, "source_hashes": source_hashes(catalog.data_dir),
            "taxonomy_hash": taxonomy_hash(), "python_version": platform.python_version(),
            "sklearn_version": sklearn.__version__,
            "topic_terms": [terms[component.argsort()[-8:][::-1]].tolist() for component in self.topic_model.components_],
            "evaluation_note": "Unsupervised fit diagnostics only. No observed relevance labels; no recommendation accuracy claim.",
        }
        return self

    def similarity(self, text):
        lexical = self.vectorizer.transform([normalize_text(text)])
        if not lexical.nnz:
            return np.zeros(len(self.ids))
        topics = normalize(self.topic_model.transform(lexical))
        return np.clip(0.8 * (self.course_vectors @ lexical.T).toarray().ravel()
                       + 0.2 * (self.course_topics @ topics.T).ravel(), 0, 1)

    def population_interests(self, exclude_student=None):
        from .schemas import InterestChoice, Interests
        from .taxonomy import TAXONOMY
        rows = [row for sid, row in self.population.items() if sid != exclude_student]
        if not rows:
            raise ValueError("No other student histories are available for population interest inference")
        centroid = normalize(np.mean(rows, axis=0).reshape(1, -1))
        selected = {}
        for category, options in TAXONOMY.items():
            entries = list(options.values())
            vectors = self.vectorizer.transform([normalize_text(item.text) for item in entries])
            scores = np.asarray(vectors @ centroid.T).ravel()
            order = sorted(range(len(entries)), key=lambda i: (-scores[i], entries[i].id))[:3]
            positive = [i for i in order if scores[i] > 0]
            total = sum(scores[i] for i in positive)
            selected[category] = [InterestChoice(id=entries[i].id, weight=float(scores[i] / total)) for i in positive]
        return Interests(**selected), len(rows)

    def matching_terms(self, text, course_id, limit=6):
        query = self.vectorizer.transform([normalize_text(text)])
        product = query.multiply(self.course_vectors[self.index[course_id]]).tocoo()
        names = self.vectorizer.get_feature_names_out()
        order = sorted(zip(product.col, product.data), key=lambda pair: (-pair[1], names[pair[0]]))
        return [str(names[column]) for column, value in order[:limit] if value > 0]

    def save(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)
        path.with_suffix(".report.json").write_text(json.dumps(self.report, indent=2) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path, catalog):
        # Only load artifacts trained locally by this project, never uploaded files.
        model = joblib.load(path)
        if not isinstance(model, cls) or model.report.get("model_version") != MODEL_VERSION:
            raise ValueError("Unsupported model artifact; retrain the model")
        if model.report["sklearn_version"] != sklearn.__version__:
            raise ValueError("scikit-learn version changed; retrain the model")
        if model.report["source_hashes"] != source_hashes(catalog.data_dir) or model.report["taxonomy_hash"] != taxonomy_hash():
            raise ValueError("Dataset or interest taxonomy changed; retrain the model")
        return model

