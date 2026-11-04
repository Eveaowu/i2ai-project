"""InterestMatcher: scores how well each course matches a free-text interest.
Swap in embeddings later by keeping the same `score(text) -> dict` signature."""
from __future__ import annotations


class InterestMatcher:
    def __init__(self, courses: dict):
        from sklearn.feature_extraction.text import TfidfVectorizer
        self.ids = list(courses)
        docs = [f"{c.title} {c.title} {c.description}" for c in courses.values()]  # title weighted x2
        self.vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
        self.matrix = self.vectorizer.fit_transform(docs)

    def score(self, interest: str) -> dict[str, float]:
        if not interest or not interest.strip():
            return {cid: 0.0 for cid in self.ids}
        from sklearn.metrics.pairwise import linear_kernel
        sims = linear_kernel(self.vectorizer.transform([interest]), self.matrix).ravel()
        return dict(zip(self.ids, sims.tolist()))
