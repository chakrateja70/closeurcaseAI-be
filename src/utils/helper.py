import base64
from pathlib import Path
from urllib.parse import urlparse

import httpx

from src.core.exceptions import BadRequestAPIException, GatewayTimeoutAPIException

MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024


async def build_image_part(client: httpx.AsyncClient, url: str) -> dict:
    try:
        head = await client.head(url, follow_redirects=True)
        content_length = int(head.headers.get("content-length", 0))
    except (httpx.HTTPError, ValueError):
        content_length = 0

    if content_length > MAX_FILE_SIZE_BYTES:
        raise BadRequestAPIException(f"File exceeds 15MB size limit: {url}")

    return {"type": "image_url", "image_url": {"url": url}}


async def build_file_part(client: httpx.AsyncClient, url: str) -> dict:
    try:
        file_response = await client.get(url, follow_redirects=True)
        file_response.raise_for_status()
    except httpx.TimeoutException as e:
        raise GatewayTimeoutAPIException(f"Timed out fetching file: {url}") from e
    except httpx.HTTPError as e:
        raise BadRequestAPIException(f"Could not fetch file: {url}") from e

    if len(file_response.content) > MAX_FILE_SIZE_BYTES:
        raise BadRequestAPIException(f"File exceeds 15MB size limit: {url}")

    filename = Path(urlparse(url).path).name or "document"
    encoded = base64.b64encode(file_response.content).decode("utf-8")
    return {
        "type": "file",
        "file": {
            "filename": filename,
            "file_data": f"data:application/octet-stream;base64,{encoded}",
        },
    }
