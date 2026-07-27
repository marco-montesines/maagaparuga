"""FastAPI surface. Endpoints trigger a scoring run for a care recipient; the
computed score is returned and (as a side effect in the service) persisted, with
an alert raised when a review threshold is crossed.

The concrete vitals reader and database are built lazily in ``get_service`` so
this module imports with no infrastructure dependencies — tests override
``get_service`` with an in-memory fake.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .domain.models import Dass21Result, News2Result, RiskAssessment
from .service import AssessmentService, InsufficientData

app = FastAPI(
    title="MaagapAruga assessment service",
    summary="NEWS2, DASS-21, and fuzzy-risk scoring. Illustrative — not a medical device.",
)


@app.exception_handler(InsufficientData)
def _insufficient_data(_request: Request, exc: InsufficientData) -> JSONResponse:
    # The inputs for a score are not available yet — a client concern, 422.
    return JSONResponse(status_code=422, content={"detail": str(exc)})

_service: AssessmentService | None = None


def get_service() -> AssessmentService:
    """Return the process-wide service, building the configured adapters on
    first use. Overridden in tests."""
    global _service
    if _service is None:  # pragma: no cover - exercised only outside unit tests
        from .wiring import build_service

        _service = build_service()
    return _service


ServiceDep = Annotated[AssessmentService, Depends(get_service)]


# -- Response models --------------------------------------------------------


class ParameterScoreModel(BaseModel):
    name: str
    value: float | str | None
    points: int


class News2Response(BaseModel):
    total: int
    clinical_risk: str
    any_parameter_3: bool
    complete: bool
    missing: list[str]
    parameters: list[ParameterScoreModel]

    @classmethod
    def of(cls, r: News2Result) -> News2Response:
        return cls(
            total=r.total,
            clinical_risk=r.clinical_risk.value,
            any_parameter_3=r.any_parameter_3,
            complete=r.complete,
            missing=list(r.missing),
            parameters=[ParameterScoreModel(name=p.name, value=p.value, points=p.points)
                        for p in r.parameters],
        )


class SubscaleModel(BaseModel):
    raw: int
    score: int
    severity: str


class Dass21Response(BaseModel):
    depression: SubscaleModel
    anxiety: SubscaleModel
    stress: SubscaleModel

    @classmethod
    def of(cls, r: Dass21Result) -> Dass21Response:
        def m(sub: object) -> SubscaleModel:
            return SubscaleModel(raw=sub.raw, score=sub.score, severity=sub.severity.value)  # type: ignore[attr-defined]

        return cls(depression=m(r.depression), anxiety=m(r.anxiety), stress=m(r.stress))


class RiskResponse(BaseModel):
    level: str
    score: float
    triggers_alert: bool
    physiological_input: float
    psychological_input: float

    @classmethod
    def of(cls, r: RiskAssessment) -> RiskResponse:
        return cls(
            level=r.level.value,
            score=round(r.score, 2),
            triggers_alert=r.triggers_alert,
            physiological_input=r.physiological_input,
            psychological_input=r.psychological_input,
        )


# -- Routes -----------------------------------------------------------------


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/assess/{recipient_id}/news2", response_model=News2Response)
def assess_news2(recipient_id: str, service: ServiceDep) -> News2Response:
    return News2Response.of(service.assess_news2(recipient_id))


@app.post("/assess/{recipient_id}/dass21", response_model=Dass21Response)
def assess_dass21(recipient_id: str, service: ServiceDep) -> Dass21Response:
    return Dass21Response.of(service.assess_dass21(recipient_id))


@app.post("/assess/{recipient_id}/risk", response_model=RiskResponse)
def assess_risk(recipient_id: str, service: ServiceDep) -> RiskResponse:
    return RiskResponse.of(service.assess_risk(recipient_id))
