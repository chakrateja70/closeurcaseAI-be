from pinecone import Pinecone, ServerlessSpec

from src.config.settings import xsettings
from src.core.exceptions import ServiceUnavailableAPIException

EMBEDDING_DIMENSION = 1536
CASES_NAMESPACE = "cases"  # Default namespace for all cases in the Pinecone index

pinecone_client = Pinecone(api_key=xsettings.PINECONE_API_KEY)


def pinecone_connection() -> None:
    """Create the Pinecone index if it doesn't exist yet."""
    try:
        if not pinecone_client.has_index(xsettings.PINECONE_INDEX_NAME):
            pinecone_client.create_index(
                name=xsettings.PINECONE_INDEX_NAME,
                dimension=EMBEDDING_DIMENSION,
                metric="dotproduct",
                spec=ServerlessSpec(cloud="aws", region="us-east-1"),
            )
    except Exception as e:
        raise ServiceUnavailableAPIException(f"Could not initialize Pinecone index: {e}") from e


def get_index():
    """Single index holds both dense and sparse values per record (hybrid search)."""
    return pinecone_client.Index(xsettings.PINECONE_INDEX_NAME)
