import logging
import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from app.endpoints.storyboard import router as storyboard_router

load_dotenv()

# ─── Logging ───────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("main")

# ─── App ───────────────────────────────────────────────────────────────────
app = FastAPI(
    title="AI Storyboard Generator",
    description=(
        "Converts a short narrative paragraph into a coherent multi-panel visual storyboard "
        "using LLM-based scene understanding and AI image generation."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ─── CORS ──────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # Tighten this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ───────────────────────────────────────────────────────────────
app.include_router(storyboard_router, prefix="/api/v1", tags=["Storyboard"])

# ─── Static Files ──────────────────────────────────────────────────────────
# Ensure static directory exists
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", tags=["Health"])
async def health_check():
    """Quick health check endpoint."""
    return {"status": "ok", "service": "AI Storyboard Generator"}


logger.info("AI Storyboard Generator API started.")
