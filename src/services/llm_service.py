from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from src.config.settings import xsettings
from src.services.langfuse_service import get_langfuse_callbacks


class LLMService:
    """Service to initialize task-specific LLM models."""

    @staticmethod
    def get_detection_model(model: str = xsettings.DETECTION_MODEL) -> ChatOpenAI:
        """Initialize LLM model for case detection."""
        return ChatOpenAI(
            model=model,
            api_key=SecretStr(xsettings.OPENAI_API_KEY),
            callbacks=get_langfuse_callbacks(),
        )

    @staticmethod
    def get_summarization_model(
        model: str = xsettings.SUMMARIZATION_MODEL, max_tokens: int = 30000
    ) -> ChatOpenAI:
        """Initialize LLM model for case summarization."""
        return ChatOpenAI(
            model=model,
            api_key=SecretStr(xsettings.OPENAI_API_KEY),
            max_completion_tokens=max_tokens,
            callbacks=get_langfuse_callbacks(),
        )


# Global singleton instance (or call directly via LLMService.get_summarization_model())
xllm_service = LLMService()
