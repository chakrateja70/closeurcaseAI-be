from fastapi import APIRouter
from pydantic import BaseModel, Field, HttpUrl

from src.services.counter_generation import generate_counter

router = APIRouter(prefix="/counter-generation", tags=["counter-generation"])


class GenerateCounterRequest(BaseModel):
    url: HttpUrl = Field(description="One affidavit document or image URL")


class LegalBasis(BaseModel):
    act: str
    provision: str
    corresponding_provision: str | None = None
    application: str
    needs_verification: bool = False


class CaseReference(BaseModel):
    citation: str
    proposition: str
    source: str
    needs_verification: bool = True


class CounterArgument(BaseModel):
    paragraph_number: str
    argument: str
    counter_argument: str
    legal_basis: list[LegalBasis] = []
    case_references: list[CaseReference] = []


class CounterGeneration(BaseModel):
    applicable_law_regime: str | None = None
    counter_arguments: list[CounterArgument]


class CounterGenerationResponse(BaseModel):
    status_code: int
    message: str
    data: CounterGeneration


@router.post("/generate-counter", response_model=CounterGenerationResponse)
async def generate_counter_route(req: GenerateCounterRequest) -> CounterGenerationResponse:
    result = await generate_counter(url=str(req.url))
    return CounterGenerationResponse(
        status_code=200, message="Counter generated successfully", data=CounterGeneration(**result)
    )
