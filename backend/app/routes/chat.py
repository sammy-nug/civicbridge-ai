from fastapi import APIRouter, Depends

from app.schemas.api import ChatRequest, ChatResponse
from app.services.rag import answer_question
from app.utils.rate_limit import enforce_daily_limit, enforce_rate_limit

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse, dependencies=[Depends(enforce_rate_limit), Depends(enforce_daily_limit)])
def chat(request: ChatRequest) -> ChatResponse:
    return answer_question(request.message, request.language, request.session_id)
