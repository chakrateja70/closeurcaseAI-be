from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from src.core.security import build_docs_router
from src.db.pinecone import pinecone_connection
from src.router import api_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    pinecone_connection()
    yield


app = FastAPI(docs_url=None, redoc_url=None, lifespan=lifespan)

app.include_router(api_router)
app.include_router(build_docs_router(app))


@app.get("/")
async def root():
    return {"message": "Closeurcase API is running!"}


if __name__ == "__main__":
    uvicorn.run("main:app", port=8000, reload=False)
