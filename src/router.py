from fastapi import APIRouter

from src.api import case_detection, case_ingestion, case_summarization, counter_generation

api_router = APIRouter(prefix="/ai")

api_router.include_router(case_detection.router)
api_router.include_router(case_summarization.router)
api_router.include_router(case_ingestion.router)
api_router.include_router(counter_generation.router)
