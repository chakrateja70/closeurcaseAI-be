from fastapi import APIRouter
from pydantic import BaseModel, Field, HttpUrl

from src.services.counter_generation import generate_counter

router = APIRouter(prefix="/counter-generation", tags=["counter-generation"])


class GenerateCounterRequest(BaseModel):
    url: HttpUrl = Field(description="One affidavit document or image URL")


class CounterArgument(BaseModel):
    paragraph_number: str
    argument: str
    counter_argument: str


class CounterGeneration(BaseModel):
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
