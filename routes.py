"""
AI Illustration Agent — API Routes
====================================
Defines all HTTP endpoints:
  GET  /           → health check
  POST /generate   → main illustration generation endpoint
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger("illustration_agent.routes")

router = APIRouter()


# ═══════════════════════════════════════════════════════
# Request / Response Schemas
# ═══════════════════════════════════════════════════════

class GenerateRequest(BaseModel):
    """Payload accepted by POST /generate."""

    prompt: str = Field(
        ...,
        min_length=3,
        max_length=1000,
        description="Text description of the illustration to generate.",
        examples=["A dragon soaring over a misty mountain range at dawn"],
    )
    style: Optional[str] = Field(
        default=None,
        description=(
            "Desired art style. Supported: watercolor, oil_painting, pencil_sketch, "
            "digital_art, anime, photorealistic, impressionist, minimalist, "
            "concept_art, comic_book, pixel_art, surrealism."
        ),
        examples=["watercolor"],
    )
    aspect_ratio: str = Field(
        default="16:9",
        description="Target aspect ratio for the illustration.",
        examples=["16:9", "1:1", "4:3", "9:16"],
    )
    detail_level: str = Field(
        default="detailed",
        description="Level of detail: 'simple', 'moderate', or 'detailed'.",
        examples=["detailed"],
    )

    @field_validator("aspect_ratio")
    @classmethod
    def validate_aspect_ratio(cls, v: str) -> str:
        allowed = {"16:9", "9:16", "1:1", "4:3", "3:4", "21:9"}
        if v not in allowed:
            raise ValueError(f"aspect_ratio must be one of {allowed}")
        return v

    @field_validator("detail_level")
    @classmethod
    def validate_detail_level(cls, v: str) -> str:
        allowed = {"simple", "moderate", "detailed"}
        if v.lower() not in allowed:
            raise ValueError(f"detail_level must be one of {allowed}")
        return v.lower()


class GenerateResponse(BaseModel):
    """Response returned by POST /generate."""

    success: bool
    prompt: str
    illustration_description: str
    style_tags: List[str]
    mood: str
    color_palette: str
    suggested_tools: List[str]
    metadata: Dict[str, Any]
    processing_time_ms: int
    errors: List[str]


class HealthResponse(BaseModel):
    """Response returned by GET /."""

    status: str
    version: str
    gemini_configured: bool
    timestamp: float


# ═══════════════════════════════════════════════════════
# Lazy Agent Singleton
# ═══════════════════════════════════════════════════════
# We import the agent lazily inside the endpoint so that:
#   • The app can still start even if GEMINI_API_KEY is missing.
#   • Tests can patch the environment before the agent initialises.

_agent_instance = None


def _get_agent():
    global _agent_instance
    if _agent_instance is None:
        from agent import IllustrationAgent  # local import (same package)
        _agent_instance = IllustrationAgent()
    return _agent_instance


# ═══════════════════════════════════════════════════════
# Endpoints
# ═══════════════════════════════════════════════════════

@router.get(
    "/",
    response_model=HealthResponse,
    summary="Health Check",
    tags=["System"],
)
async def health_check() -> HealthResponse:
    """
    Returns the service status and configuration state.
    Use this endpoint to verify the container is alive and Gemini is configured.
    """
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    return HealthResponse(
        status="ok",
        version="1.0.0",
        gemini_configured=bool(gemini_key),
        timestamp=time.time(),
    )


@router.post(
    "/generate",
    response_model=GenerateResponse,
    summary="Generate Illustration Description",
    tags=["Agent"],
)
async def generate_illustration(
    request: Request,
    body: GenerateRequest,
) -> GenerateResponse:
    """
    Accepts a text prompt and runs the three-stage ADK agent pipeline:

    1. **InputHandler** — validates and normalises the prompt.
    2. **ReasoningStep** — infers style, mood, colour palette via Gemini.
    3. **OutputGenerator** — produces a production-ready illustration description.

    Returns a rich JSON object with the description plus metadata.
    """
    logger.info(
        "[POST /generate] prompt=%r style=%s ratio=%s detail=%s",
        body.prompt[:80],
        body.style,
        body.aspect_ratio,
        body.detail_level,
    )

    try:
        agent = _get_agent()
    except EnvironmentError as exc:
        logger.error("Agent initialisation failed: %s", exc)
        raise HTTPException(
            status_code=503,
            detail=(
                "GEMINI_API_KEY is not configured. "
                "Set the environment variable and restart the service."
            ),
        )

    try:
        result = agent.run(
            prompt=body.prompt,
            style=body.style,
            aspect_ratio=body.aspect_ratio,
            detail_level=body.detail_level,
        )
    except Exception as exc:
        logger.exception("Unexpected agent error")
        raise HTTPException(status_code=500, detail=f"Agent error: {exc}")

    if not result.success and not result.illustration_description:
        raise HTTPException(
            status_code=422,
            detail={"errors": result.errors},
        )

    logger.info(
        "[POST /generate] Done in %dms. success=%s",
        result.processing_time_ms,
        result.success,
    )

    return GenerateResponse(
        success=result.success,
        prompt=result.prompt,
        illustration_description=result.illustration_description,
        style_tags=result.style_tags,
        mood=result.mood,
        color_palette=result.color_palette,
        suggested_tools=result.suggested_tools,
        metadata=result.metadata,
        processing_time_ms=result.processing_time_ms,
        errors=result.errors,
    )
