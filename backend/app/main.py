from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.api.routes.video import router as video_router

from backend.app.api.routes.health import router as health_router
from backend.app.api.routes.image import router as image_router
from backend.app.api.routes.plates import router as plates_router
from backend.app.database import init_db


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()  # tạo backend/data/plates.db và 2 bảng camera_plates, video_plates nếu chưa có
    yield


app = FastAPI(
    lifespan=lifespan,
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
app.include_router(plates_router, prefix="/api")


@app.get("/")
def home():
    return {
        "message": "License Plate Recognition API",
        "docs": "/docs",
    }
