from fastapi import APIRouter
from pydantic import BaseModel, Field, HttpUrl, model_validator

from src.services.case_summarization import generate_summary

router = APIRouter(prefix="/summarization", tags=["case-summarization"])


class CaseSummary(BaseModel):
    brief: str
    key_points: list[str]


class SummarizeCaseResponse(BaseModel):
    message: str
    summary: CaseSummary


class SummarizeCaseRequest(BaseModel):
    urls: list[HttpUrl] = Field(
        default_factory=list,
        max_length=5,
        description="Up to 5 reference URLs",
    )
    case_text: str | None = Field(
        default=None,
        max_length=30000,
        description="Full text of the case to summarize (maximum 30,000 characters)",
    )

    @model_validator(mode="after")
    def validate_url_or_case_text(self):
        has_urls = bool(self.urls)
        has_text = bool(self.case_text and self.case_text.strip())
        if not has_urls and not has_text:
            raise ValueError("Either at least one URL or 'case_text' is required.")
        return self


@router.post("/summarize-case", response_model=SummarizeCaseResponse)
async def summarize_case(req: SummarizeCaseRequest):
    summary = await generate_summary(case_text=req.case_text, urls=req.urls)
    return SummarizeCaseResponse(message="Case summarized successfully", summary=summary)
