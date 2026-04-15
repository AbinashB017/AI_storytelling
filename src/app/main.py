import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from app.endpoints.storyboard import router as storyboard_router

load_dotenv()

# ─── Logging ───────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("main")

# ─── App ───────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Scenova — AI Storyboard Generator",
    description=(
        "Converts a short narrative paragraph into a coherent multi-panel visual storyboard "
        "using LLM-based scene understanding and AI image generation."
    ),
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ─── CORS ──────────────────────────────────────────────────────────────────
# Read allowed origins from env (comma-separated). Falls back to '*' in dev.
_raw_origins = os.getenv("ALLOWED_ORIGINS", "*")
if _raw_origins == "*":
    allow_origins = ["*"]
else:
    allow_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
logger.info("[CORS] Allowed origins: %s", allow_origins)

# ─── Routers ───────────────────────────────────────────────────────────────
app.include_router(storyboard_router, prefix="/api/v1", tags=["Storyboard"])

# ─── Static Files ──────────────────────────────────────────────────────────
# Resolve static/ relative to this file so it works from any working directory
_static_dir = Path(__file__).resolve().parent.parent.parent / "static"
if not _static_dir.exists():
    _static_dir.mkdir(parents=True, exist_ok=True)
    logger.info("[STATIC] Created static directory at %s", _static_dir)

app.mount("/static", StaticFiles(directory=str(_static_dir), html=True), name="static")
logger.info("[STATIC] Mounted static directory: %s", _static_dir)


# ─── Health Endpoint ───────────────────────────────────────────────────────
@app.get("/health", tags=["Health"])
async def health_check():
    """Uptime monitoring endpoint. Returns 200 when service is live."""
    return {"status": "ok"}


@app.get("/", tags=["Health"], include_in_schema=False)
async def root():
    """Redirect root to the frontend UI."""
    return RedirectResponse(url="/static/index.html")


logger.info("[STARTUP] Scenova API v2.0.0 ready.")
