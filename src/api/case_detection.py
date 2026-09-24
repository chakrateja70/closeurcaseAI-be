from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.services.case_detection import detect_case

router = APIRouter(prefix="/detection", tags=["case-detection"])


class DetectCaseRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=1,
        max_length=600,
        description="User's description of the issue (max 600 characters)",
        examples=["My landlord is refusing to return my security deposit after eviction. "],
    )


class DetectCaseData(BaseModel):
    categoryId: str | None
    categoryName: str | None
    subCategoryId: str | None
    subCategoryName: str | None


class DetectCaseResponse(BaseModel):
    status_code: int
    message: str
    data: DetectCaseData


@router.post("/detect-case", response_model=DetectCaseResponse)
async def detect_case_route(req: DetectCaseRequest):
    result = await detect_case(req.query)
    message = (
        "Case category detected successfully"
        if result["categoryId"]
        else "No matching case category found"
    )
    return DetectCaseResponse(status_code=200, message=message, data=result)
