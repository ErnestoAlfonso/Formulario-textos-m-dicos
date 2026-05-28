from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import process

app = FastAPI(title="Medical Audio Processor")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

app.include_router(process.router)
