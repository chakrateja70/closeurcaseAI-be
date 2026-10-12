import os
from decimal import Decimal

from dotenv import load_dotenv

load_dotenv(override=True)


class Settings:
    """Application settings loaded from environment variables."""

    def __init__(self):

        self.OPENAI_API_KEY: str = self._get_required("OPENAI_API_KEY")
        self.SUMMARIZATION_MODEL: str = "gpt-5.4-mini"
        self.DETECTION_MODEL: str = "gpt-5.4-nano"
        self.EXTRACTION_MODEL: str = "gpt-5.4-mini"
        self.COUNTER_GENERATION_MODEL: str = "gpt-5.1"
        self.EMBEDDING_MODEL: str = "text-embedding-3-small"

        # Credits granted per $1 of OpenAI spend, and how many decimals a credit amount keeps.
        # Our profit: credits charged = OpenAI cost x CREDIT_MARKUP x CREDITS_PER_USD (1.5 = +50%).
        self.CREDIT_MARKUP: Decimal = Decimal(os.getenv("CREDIT_MARKUP", "1"))
        self.CREDITS_PER_USD: Decimal = Decimal(os.getenv("CREDITS_PER_USD", "1000"))
        self.CREDIT_DECIMALS: int = int(os.getenv("CREDIT_DECIMALS", "6"))

        self.SWAGGER_USERNAME: str = self._get_required("SWAGGER_USERNAME")
        self.SWAGGER_PASSWORD: str = self._get_required("SWAGGER_PASSWORD")

        self.PINECONE_API_KEY: str = self._get_required("PINECONE_API_KEY")
        self.PINECONE_INDEX_NAME: str = self._get_required("PINECONE_INDEX_NAME")

        self.LANGFUSE_PUBLIC_KEY: str | None = os.getenv("LANGFUSE_PUBLIC_KEY")
        self.LANGFUSE_SECRET_KEY: str | None = os.getenv("LANGFUSE_SECRET_KEY")
        self.LANGFUSE_HOST: str = "https://cloud.langfuse.com"

    @staticmethod
    def _get_required(key: str) -> str:
        value = os.getenv(key)
        if not value:
            raise ValueError(
                f"{key} not found in environment variables. Please check your .env file."
            )
        return value


xsettings = Settings()
