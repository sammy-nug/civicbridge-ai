from fastapi import APIRouter, Depends

from app.schemas.api import VerifyRequest, VerifyResponse
from app.services.rag import verify_claim
from app.utils.rate_limit import enforce_daily_limit, enforce_rate_limit

router = APIRouter(prefix="/api", tags=["verify"])


@router.post("/verify", response_model=VerifyResponse, dependencies=[Depends(enforce_rate_limit), Depends(enforce_daily_limit)])
def verify(request: VerifyRequest) -> VerifyResponse:
    return verify_claim(request.claim, request.language)
