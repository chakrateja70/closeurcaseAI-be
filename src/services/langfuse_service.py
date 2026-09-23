from langfuse import Langfuse
from langfuse.langchain import CallbackHandler

from src.config.settings import xsettings

xlangfuse_client: Langfuse | None = None
if xsettings.LANGFUSE_PUBLIC_KEY and xsettings.LANGFUSE_SECRET_KEY:
    xlangfuse_client = Langfuse(
        public_key=xsettings.LANGFUSE_PUBLIC_KEY,
        secret_key=xsettings.LANGFUSE_SECRET_KEY,
        host=xsettings.LANGFUSE_HOST,
    )


def get_langfuse_callbacks() -> list:
    """Return LangChain callbacks for Langfuse tracing, or [] if not configured."""
    if xlangfuse_client is None:
        return []
    return [CallbackHandler()]
