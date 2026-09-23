from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/detection", tags=["case-detection"])

class DetectCaseRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=600, description="User's description of the issue (max 600 characters)", examples=["My landlord is refusing to return my security deposit after eviction. "])

@router.post("/detect-case")
async def detect_case(req:DetectCaseRequest):
    return {"message": "Case detected"}
