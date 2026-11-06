from fastapi import APIRouter, Depends, HTTPException

from app.models.database import record_feedback
from app.schemas.api import FeedbackRequest, FeedbackResponse
from app.services.guardrails import scrub_sensitive
from app.utils.rate_limit import enforce_rate_limit

router = APIRouter(prefix="/api", tags=["feedback"])


@router.post("/feedback", response_model=FeedbackResponse, status_code=201, dependencies=[Depends(enforce_rate_limit)])
def feedback(request: FeedbackRequest) -> FeedbackResponse:
    comment = scrub_sensitive(request.feedback.strip())[0] if request.feedback and request.feedback.strip() else None
    if not record_feedback(request.response_id, request.rating, comment):
        raise HTTPException(status_code=404, detail="That response could not be found.")
    return FeedbackResponse(status="recorded")
