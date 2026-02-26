from fastapi import APIRouter
from pydantic import BaseModel
from app.domains.ai_text2sql.service import AIText2SQLService

router = APIRouter(prefix="/ai", tags=["ai"])

class AskIn(BaseModel):
    question: str

@router.post("/query")
async def query(payload: AskIn):
    svc = AIText2SQLService()
    return await svc.ask(payload.question)
