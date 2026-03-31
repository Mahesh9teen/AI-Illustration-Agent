"""
AI Illustration Agent - Main Application Entry Point
FastAPI application bootstrapper with logging, middleware, and startup config.
"""

import logging
import os
import sys

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes import router

# ─────────────────────────────────────────
# Logging Configuration
# ─────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("illustration_agent")


# ─────────────────────────────────────────
# FastAPI App Initialization
# ─────────────────────────────────────────
app = FastAPI(
    title="AI Illustration Agent",
    description=(
        "An agent-based service that accepts a text prompt and returns "
        "a rich illustration description powered by Google Gemini."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Allow all origins for Cloud Run / demo purposes.
# Restrict to specific domains in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register route handlers
app.include_router(router)


# ─────────────────────────────────────────
# Startup / Shutdown Events
# ─────────────────────────────────────────
@app.on_event("startup")
async def on_startup() -> None:
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    if not gemini_key:
        logger.warning(
            "GEMINI_API_KEY environment variable is not set. "
            "The /generate endpoint will fail until it is configured."
        )
    else:
        logger.info("GEMINI_API_KEY detected — Gemini integration ready.")
    logger.info("AI Illustration Agent started successfully.")


@app.on_event("shutdown")
async def on_shutdown() -> None:
    logger.info("AI Illustration Agent shutting down.")


# ─────────────────────────────────────────
# Local Dev Entry Point
# ─────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
