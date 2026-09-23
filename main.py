import uvicorn
from fastapi import FastAPI

from src.router import api_router

app = FastAPI()

app.include_router(api_router)

@app.get("/")
async def root():
    return {"message": "Closeurcase API is running!"}


if __name__ == "__main__":
    uvicorn.run("main:app", port=8000, reload=True)
