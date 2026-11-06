"""Local development API. Run: uvicorn recommender.api:app --host 127.0.0.1"""
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from starlette.concurrency import run_in_threadpool

from .catalog import DEFAULT_DATA, ROOT
from .documents import MAX_BYTES, extract_document
from .schemas import RecommendationRequest
from .service import RecommendationService
from .taxonomy import taxonomy_payload


@asynccontextmanager
async def lifespan(app):
    model_path = Path(os.environ.get("RECOMMENDER_MODEL", ROOT / "artifacts/recommender.joblib"))
    data_dir = Path(os.environ.get("RECOMMENDER_DATA", DEFAULT_DATA))
    app.state.recommender = RecommendationService.from_artifact(model_path, data_dir)
    yield


app = FastAPI(title="AIM Elective Recommendation API", version="1.0", lifespan=lifespan)


@app.get("/health")
def health(request: Request):
    return {"status": "ok", "model_version": request.app.state.recommender.model.report["model_version"]}


@app.get("/interests")
def interests():
    return taxonomy_payload()


@app.post("/extract")
async def extract(file: Annotated[UploadFile, File()], kind: Annotated[Literal["resume", "transcript"], Form()]):
    try:
        data = await file.read(MAX_BYTES + 1)
        return await run_in_threadpool(extract_document, data, file.filename or "upload.txt", kind)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        await file.close()


@app.post("/recommendations")
def recommend(payload: RecommendationRequest, request: Request):
    try:
        return request.app.state.recommender.recommend(payload.profile, term=payload.term, top_k=payload.top_k)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

