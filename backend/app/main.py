"""REST API (FastAPI). Run with:  uvicorn app.main:app --reload   (from the backend/ folder)

Interactive API docs are generated automatically at /docs.
"""
import logging
import secrets
from contextlib import asynccontextmanager
from typing import Callable

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session

from . import exporter, service
from .config import DEFAULT_WEIGHTS, METRIC_KEYS, Settings
from .database import Database
from .models import Experiment
from .prompt_generator import TECHNIQUE_LABELS, generate_variants
from .providers import LLMProvider, get_provider
from .schemas import (ExperimentOut, ExperimentRequest, ExperimentSummary, PreviewRequest, RescoreRequest)

log = logging.getLogger("prompt_lab")


def create_app(settings: Settings | None = None,
               provider_factory: Callable[[str, Settings], LLMProvider] = get_provider) -> FastAPI:
    """App factory. Tests pass their own settings / provider so nothing real is touched."""
    settings = settings or Settings.from_env()
    db = Database(settings.database_url)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        db.create_tables()
        yield

    app = FastAPI(
        title="Adaptive Prompt Optimization and Evaluation Framework",
        description="Generate prompt variants, run them through an LLM (or the demo simulator), "
                    "score the outputs with transparent metrics and recommend the best prompt.",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware, allow_origins=list(settings.cors_origins), allow_methods=["*"], allow_headers=["*"],
        expose_headers=["Content-Disposition"],
    )

    def get_session():
        session = db.session()
        try:
            yield session
        finally:
            session.close()

    def load_experiment(session: Session, experiment_id: int) -> Experiment:
        experiment = session.get(Experiment, experiment_id)
        if experiment is None:
            raise HTTPException(404, f"Experiment {experiment_id} not found.")
        return experiment

    @app.exception_handler(Exception)
    async def unexpected_error(_: Request, exc: Exception):
        log.exception("Unhandled error", exc_info=exc)  # details stay in the server log only
        return JSONResponse({"detail": "Internal server error."}, status_code=500)

    # ---------- info ----------

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/config")
    def get_config():
        """What the frontend needs to know. Never includes the API key."""
        return {
            "demo_available": True,
            "real_available": settings.real_mode_available,
            "real_unavailable_reason": settings.real_mode_problem,
            "real_requires_access_code": settings.real_mode_access_code is not None,
            "provider": settings.llm_provider,
            "model": settings.llm_model,
            "price_known": settings.price_known,
            "price_input_per_mtok": settings.price_input_per_mtok,
            "price_output_per_mtok": settings.price_output_per_mtok,
            "default_weights": DEFAULT_WEIGHTS,
            "metrics": METRIC_KEYS,
            "techniques": [{"key": k, "label": v} for k, v in TECHNIQUE_LABELS.items()],
        }

    # ---------- prompts ----------

    @app.post("/api/prompts/preview")
    def preview_prompts(body: PreviewRequest):
        """Show the generated prompt variants without calling any LLM."""
        variants = generate_variants(body.task, body.techniques, body.target_words)
        return [{"technique": v.technique, "label": v.label, "description": v.description, "prompt": v.prompt}
                for v in variants]

    # ---------- experiments ----------

    @app.post("/api/experiments", response_model=ExperimentOut, status_code=201)
    def create_experiment(body: ExperimentRequest, session: Session = Depends(get_session),
                          x_access_code: str | None = Header(default=None)):
        if body.mode == "real":
            if not settings.real_mode_available:
                raise HTTPException(503, f"Real mode is not configured on this server: {settings.real_mode_problem}. "
                                         "Use Demo mode, or set the LLM_* variables (see .env.example).")
            code = settings.real_mode_access_code
            if code and not secrets.compare_digest(x_access_code or "", code):
                raise HTTPException(401, "Real mode needs a valid access code.")
        provider = provider_factory(body.mode, settings)
        experiment = service.run_experiment(
            session, provider, settings, task=body.task, reference_answer=body.reference_answer or None,
            techniques=body.techniques, weights=body.weights, target_words=body.target_words, mode=body.mode,
        )
        return service.experiment_to_dict(experiment)

    @app.get("/api/experiments", response_model=list[ExperimentSummary])
    def list_experiments(session: Session = Depends(get_session)):
        return [service.experiment_summary(e) for e in service.list_experiments(session)]

    # NOTE: this fixed path must be declared before /api/experiments/{experiment_id}.
    @app.get("/api/experiments/export")
    def export_all(format: str = Query("csv", pattern="^(csv|json)$"), session: Session = Depends(get_session)):
        return _export_response([service.experiment_to_dict(e) for e in service.list_experiments(session)],
                                format, "experiments")

    @app.get("/api/experiments/{experiment_id}", response_model=ExperimentOut)
    def get_experiment(experiment_id: int, session: Session = Depends(get_session)):
        return service.experiment_to_dict(load_experiment(session, experiment_id))

    @app.get("/api/experiments/{experiment_id}/export")
    def export_one(experiment_id: int, format: str = Query("csv", pattern="^(csv|json)$"),
                   session: Session = Depends(get_session)):
        data = service.experiment_to_dict(load_experiment(session, experiment_id))
        return _export_response([data], format, f"experiment_{experiment_id}")

    @app.post("/api/experiments/{experiment_id}/rescore", response_model=ExperimentOut)
    def rescore(experiment_id: int, body: RescoreRequest, session: Session = Depends(get_session)):
        experiment = service.rescore_experiment(session, load_experiment(session, experiment_id), body.weights)
        return service.experiment_to_dict(experiment)

    @app.delete("/api/experiments/{experiment_id}", status_code=204)
    def delete_experiment(experiment_id: int, session: Session = Depends(get_session)):
        session.delete(load_experiment(session, experiment_id))
        session.commit()
        return Response(status_code=204)

    return app


def _export_response(experiments: list[dict], fmt: str, filename: str) -> Response:
    if fmt == "json":
        body, media = exporter.to_json(experiments), "application/json"
    else:
        body, media = exporter.to_csv(experiments), "text/csv"
    return Response(body, media_type=media,
                    headers={"Content-Disposition": f'attachment; filename="{filename}.{fmt}"'})


app = create_app()
