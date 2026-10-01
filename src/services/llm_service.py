from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from pydantic import SecretStr

from src.config.settings import xsettings
from src.services.langfuse_service import get_langfuse_callbacks


class LLMService:
    """Service to initialize task-specific LLM models.

    OpenAI caches prompt prefixes of 1024+ tokens automatically; a stable per-task
    prompt_cache_key routes same-prompt requests to the same cache for higher hit rates.
    """

    @staticmethod
    def get_detection_model(model: str = xsettings.DETECTION_MODEL) -> ChatOpenAI:
        """Initialize LLM model for case detection."""
        return ChatOpenAI(
            model=model,
            api_key=SecretStr(xsettings.OPENAI_API_KEY),
            model_kwargs={"prompt_cache_key": "case-detection"},
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
            model_kwargs={"prompt_cache_key": "case-summarization"},
            callbacks=get_langfuse_callbacks(),
        )

    @staticmethod
    def get_case_extraction_model(
        model: str = xsettings.EXTRACTION_MODEL, max_tokens: int = 30000
    ) -> ChatOpenAI:
        """Initialize LLM model for case extraction."""
        return ChatOpenAI(
            model=model,
            api_key=SecretStr(xsettings.OPENAI_API_KEY),
            max_completion_tokens=max_tokens,
            model_kwargs={"prompt_cache_key": "case-extraction"},
            callbacks=get_langfuse_callbacks(),
        )

    @staticmethod
    def get_counter_generation_model(model: str = xsettings.COUNTER_GENERATION_MODEL) -> ChatOpenAI:
        """Initialize LLM model for generating counter arguments."""
        # Responses API; text.format is set per call via response_format (json_object).
        return ChatOpenAI(
            model=model,
            api_key=SecretStr(xsettings.OPENAI_API_KEY),
            use_responses_api=True,
            reasoning={"effort": "low", "mode": "standard"},
            verbosity="medium",
            model_kwargs={"prompt_cache_key": "counter-generation"},
            callbacks=get_langfuse_callbacks(),
        )

    @staticmethod
    def get_embedding_model(model: str = xsettings.EMBEDDING_MODEL) -> OpenAIEmbeddings:
        """Initialize LLM model for embeddings."""
        return OpenAIEmbeddings(
            model=model,
            api_key=SecretStr(xsettings.OPENAI_API_KEY),
        )


# Global singleton instance (or call directly via LLMService.get_summarization_model())
xllm_service = LLMService()
