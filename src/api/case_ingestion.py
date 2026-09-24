from fastapi import APIRouter
from pydantic import BaseModel, Field, HttpUrl, model_validator

from src.services.case_ingestion import xragservice

router = APIRouter(prefix="/case-ingestion", tags=["case-ingestion"])


class IngestCaseRequest(BaseModel):
    case_id: str = Field(..., min_length=1, description="Unique case identifier")
    urls: list[HttpUrl] = Field(
        default_factory=list,
        max_length=5,
        description="Up to 5 case document URLs",
    )
    case_text: str | None = Field(
        default=None,
        max_length=30000,
        description="Full text of the case (maximum 30,000 characters)",
    )

    @model_validator(mode="after")
    def validate_url_or_case_text(self):
        has_urls = bool(self.urls)
        has_text = bool(self.case_text and self.case_text.strip())
        if not has_urls and not has_text:
            raise ValueError("Either at least one URL or 'case_text' is required.")
        return self


class IngestCaseResponse(BaseModel):
    status_code: int
    message: str


@router.post("/ingest-case", response_model=IngestCaseResponse)
async def ingest_case(req: IngestCaseRequest) -> IngestCaseResponse:
    await xragservice.load_and_extract(case_text=req.case_text, urls=req.urls)
    return IngestCaseResponse(status_code=200, message="Case ingested successfully")
