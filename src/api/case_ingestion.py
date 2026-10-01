from fastapi import APIRouter
from pydantic import BaseModel, Field, HttpUrl, model_validator

from src.services.case_ingestion import answer_query
from src.services.case_ingestion import delete_case as delete_case_service
from src.services.case_ingestion import ingest_case as ingest_case_service

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
        max_length=600,
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


class QueryRequest(BaseModel):
    case_id: str = Field(..., min_length=1, description="Case to search within")
    query: str = Field(..., min_length=1, max_length=2000, description="Question about the case")


class QueryData(BaseModel):
    answer: str
    sources: list[str]


class QueryResponse(BaseModel):
    status_code: int
    message: str
    data: QueryData


@router.post("/ingest-case", response_model=IngestCaseResponse)
async def ingest_case(req: IngestCaseRequest) -> IngestCaseResponse:
    await ingest_case_service(case_id=req.case_id, case_text=req.case_text, urls=req.urls)
    return IngestCaseResponse(status_code=200, message="Case ingested successfully")


@router.post("/query", response_model=QueryResponse)
async def query_case(req: QueryRequest) -> QueryResponse:
    result = await answer_query(case_id=req.case_id, query=req.query)
    return QueryResponse(status_code=200, message="Query answered", data=QueryData(**result))


@router.delete("/delete-case/{case_id}", response_model=IngestCaseResponse)
async def delete_case(case_id: str) -> IngestCaseResponse:
    await delete_case_service(case_id)
    return IngestCaseResponse(status_code=200, message="Case deleted successfully")
