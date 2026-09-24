import os

from dotenv import load_dotenv

load_dotenv(override=True)


class Settings:
    """Application settings loaded from environment variables."""

    def __init__(self):

        self.OPENAI_API_KEY: str = self._get_required("OPENAI_API_KEY")
        self.SUMMARIZATION_MODEL: str = "gpt-4.1-mini"
        self.DETECTION_MODEL: str = "gpt-4o-mini"
        self.EXTRACTION_MODEL: str = "gpt-4.1-mini"

        self.SWAGGER_USERNAME: str = self._get_required("SWAGGER_USERNAME")
        self.SWAGGER_PASSWORD: str = self._get_required("SWAGGER_PASSWORD")

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
