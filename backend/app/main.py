from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.api.routes.video import router as video_router

from backend.app.api.routes.health import router as health_router
from backend.app.api.routes.image import router as image_router

app = FastAPI(
    title="Vietnamese License Plate Recognition API",
    description="Backend API for Vietnamese license plate recognition",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api")
app.include_router(image_router, prefix="/api")
app.include_router(video_router, prefix="/api")


@app.get("/")
def home():
    return {
        "message": "License Plate Recognition API",
        "docs": "/docs",
    }
