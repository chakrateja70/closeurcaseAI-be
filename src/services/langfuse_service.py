from langfuse import Langfuse
from langfuse.langchain import CallbackHandler

from src.config.settings import xsettings

langfuse_client: Langfuse | None = None
if xsettings.LANGFUSE_PUBLIC_KEY and xsettings.LANGFUSE_SECRET_KEY:
    langfuse_client = Langfuse(
        public_key=xsettings.LANGFUSE_PUBLIC_KEY,
        secret_key=xsettings.LANGFUSE_SECRET_KEY,
        host=xsettings.LANGFUSE_HOST,
        # Default 5s is too short to upload base64 documents attached to traces.
        timeout=240,
    )


def get_langfuse_callbacks() -> list:
    """Return LangChain callbacks for Langfuse tracing, or [] if not configured."""
    if langfuse_client is None:
        return []
    return [CallbackHandler()]
