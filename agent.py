"""
AI Illustration Agent — Agent Core (ADK-style)
================================================
Implements a three-stage agent pipeline:
  1. InputHandler   — validates and enriches the raw user prompt
  2. ReasoningStep  — builds a structured illustration specification
  3. OutputGenerator — calls Gemini and formats the final result

Each stage is a standalone, testable class that communicates via a shared
AgentContext dataclass, following ADK's event-driven design philosophy.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import google.generativeai as genai

logger = logging.getLogger("illustration_agent.agent")


# ═══════════════════════════════════════════════════════
# Data Models (Agent Context)
# ═══════════════════════════════════════════════════════

@dataclass
class AgentContext:
    """
    Shared mutable context that flows through every agent stage.
    Each stage reads from and writes to this object.
    """
    # Inputs
    raw_prompt: str = ""
    style: Optional[str] = None
    aspect_ratio: str = "16:9"
    detail_level: str = "detailed"

    # Intermediate state set by ReasoningStep
    enriched_prompt: str = ""
    style_tags: List[str] = field(default_factory=list)
    mood: str = ""
    color_palette: str = ""

    # Final output set by OutputGenerator
    illustration_description: str = ""
    suggested_tools: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Lifecycle
    stage: str = "init"
    errors: List[str] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)


@dataclass
class AgentResult:
    """Final structured result returned to the API layer."""
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


# ═══════════════════════════════════════════════════════
# Stage 1 — Input Handler
# ═══════════════════════════════════════════════════════

class InputHandler:
    """
    Validates and pre-processes the raw user prompt.
    Responsibilities:
      - Sanitise input (strip, length check)
      - Normalise style preference
      - Attach initial metadata
    """

    SUPPORTED_STYLES = {
        "watercolor", "oil_painting", "pencil_sketch", "digital_art",
        "anime", "photorealistic", "impressionist", "minimalist",
        "concept_art", "comic_book", "pixel_art", "surrealism",
    }

    MAX_PROMPT_LENGTH = 1_000  # characters

    def run(self, ctx: AgentContext) -> AgentContext:
        logger.info("[InputHandler] Processing raw prompt (length=%d)", len(ctx.raw_prompt))
        ctx.stage = "input_handling"

        # --- Sanitise ---
        prompt = ctx.raw_prompt.strip()
        if not prompt:
            ctx.errors.append("Prompt must not be empty.")
            return ctx

        if len(prompt) > self.MAX_PROMPT_LENGTH:
            prompt = prompt[: self.MAX_PROMPT_LENGTH]
            logger.warning("[InputHandler] Prompt truncated to %d chars.", self.MAX_PROMPT_LENGTH)

        ctx.raw_prompt = prompt

        # --- Normalise style ---
        if ctx.style:
            ctx.style = ctx.style.lower().replace(" ", "_").replace("-", "_")
            if ctx.style not in self.SUPPORTED_STYLES:
                logger.warning(
                    "[InputHandler] Unknown style '%s'; defaulting to 'digital_art'.", ctx.style
                )
                ctx.style = "digital_art"

        # --- Metadata ---
        ctx.metadata["input_length"] = len(prompt)
        ctx.metadata["style_requested"] = ctx.style or "auto"
        ctx.metadata["aspect_ratio"] = ctx.aspect_ratio
        ctx.metadata["detail_level"] = ctx.detail_level

        logger.info("[InputHandler] Done. Style=%s", ctx.metadata["style_requested"])
        return ctx


# ═══════════════════════════════════════════════════════
# Stage 2 — Reasoning Step
# ═══════════════════════════════════════════════════════

class ReasoningStep:
    """
    Analyses the validated prompt and constructs a rich illustration specification.
    Uses Gemini (fast/lightweight call) to infer:
      - Best artistic style (if not provided)
      - Mood / atmosphere
      - Suggested colour palette
      - Descriptive style tags
    Falls back to heuristics if the API call fails.
    """

    _REASONING_PROMPT_TEMPLATE = """
You are an expert art director and creative consultant.
Analyse the following illustration prompt and return ONLY a JSON object (no markdown, no commentary).

Prompt: "{prompt}"
Requested style: {style}

Return exactly this JSON structure:
{{
  "enriched_prompt": "<rewritten prompt optimised for image generation, ~150 words>",
  "style_tags": ["<tag1>", "<tag2>", "<tag3>", "<tag4>", "<tag5>"],
  "mood": "<single evocative word, e.g. ethereal, melancholic, vibrant>",
  "color_palette": "<3-5 comma-separated color names that suit the scene>",
  "recommended_style": "<one of: watercolor, oil_painting, pencil_sketch, digital_art, anime, photorealistic, impressionist, minimalist, concept_art, comic_book, pixel_art, surrealism>"
}}
""".strip()

    def run(self, ctx: AgentContext) -> AgentContext:
        if ctx.errors:
            return ctx  # Skip if upstream errors exist

        logger.info("[ReasoningStep] Building illustration specification.")
        ctx.stage = "reasoning"

        style_label = ctx.style or "auto-detect"
        reasoning_prompt = self._REASONING_PROMPT_TEMPLATE.format(
            prompt=ctx.raw_prompt,
            style=style_label,
        )

        try:
            model = genai.GenerativeModel("gemini-2.0-flash")
            response = model.generate_content(reasoning_prompt)
            raw_json = response.text.strip()

            # Strip accidental markdown fences
            if raw_json.startswith("```"):
                lines = raw_json.splitlines()
                raw_json = "\n".join(
                    l for l in lines if not l.startswith("```")
                ).strip()

            import json
            spec = json.loads(raw_json)

            ctx.enriched_prompt = spec.get("enriched_prompt", ctx.raw_prompt)
            ctx.style_tags = spec.get("style_tags", [])
            ctx.mood = spec.get("mood", "")
            ctx.color_palette = spec.get("color_palette", "")

            # Use recommended style only when user didn't specify one
            if not ctx.style:
                ctx.style = spec.get("recommended_style", "digital_art")

            ctx.metadata["reasoning_style_used"] = ctx.style
            logger.info(
                "[ReasoningStep] Spec built. Mood=%s, Style=%s", ctx.mood, ctx.style
            )

        except Exception as exc:  # pragma: no cover
            logger.error("[ReasoningStep] Gemini reasoning failed: %s", exc)
            # Graceful fallback — use raw prompt as-is
            ctx.enriched_prompt = ctx.raw_prompt
            ctx.style = ctx.style or "digital_art"
            ctx.style_tags = ["illustration", "art"]
            ctx.mood = "neutral"
            ctx.color_palette = "varied"
            ctx.errors.append(f"Reasoning step used fallback due to: {exc}")

        return ctx


# ═══════════════════════════════════════════════════════
# Stage 3 — Output Generator
# ═══════════════════════════════════════════════════════

class OutputGenerator:
    """
    Calls Gemini with the enriched specification to produce the final
    illustration description — a production-ready prompt / visual narrative
    that can be fed directly into image generation APIs (Imagen, DALL-E, etc.).
    """

    _OUTPUT_PROMPT_TEMPLATE = """
You are a master illustrator and visual storyteller.

Given the following enriched specification, write a COMPLETE, VIVID illustration description that:
1. Paints the scene with specific visual detail (lighting, perspective, textures, focal points)
2. Calls out the colour palette and emotional atmosphere
3. Specifies the art style with technical precision
4. Is ready to use as a prompt for an AI image generator

--- Specification ---
Original Prompt : {raw_prompt}
Enriched Prompt : {enriched_prompt}
Art Style       : {style}
Mood / Tone     : {mood}
Colour Palette  : {color_palette}
Style Tags      : {style_tags}
Aspect Ratio    : {aspect_ratio}
Detail Level    : {detail_level}
---------------------

Respond with a single rich paragraph (200-300 words). Do NOT use headers or lists.
""".strip()

    _SUGGESTED_TOOLS = [
        "Google Imagen 3",
        "Stable Diffusion XL",
        "DALL-E 3",
        "Midjourney v6",
    ]

    def run(self, ctx: AgentContext) -> AgentContext:
        if ctx.errors and not ctx.enriched_prompt:
            return ctx  # Hard failure — skip generation

        logger.info("[OutputGenerator] Generating final illustration description.")
        ctx.stage = "output_generation"

        output_prompt = self._OUTPUT_PROMPT_TEMPLATE.format(
            raw_prompt=ctx.raw_prompt,
            enriched_prompt=ctx.enriched_prompt,
            style=ctx.style,
            mood=ctx.mood,
            color_palette=ctx.color_palette,
            style_tags=", ".join(ctx.style_tags),
            aspect_ratio=ctx.aspect_ratio,
            detail_level=ctx.detail_level,
        )

        try:
            model = genai.GenerativeModel("gemini-2.0-flash")
            response = model.generate_content(output_prompt)
            ctx.illustration_description = response.text.strip()
            ctx.suggested_tools = self._SUGGESTED_TOOLS
            logger.info("[OutputGenerator] Description generated (%d chars).",
                        len(ctx.illustration_description))

        except Exception as exc:  # pragma: no cover
            logger.error("[OutputGenerator] Gemini generation failed: %s", exc)
            ctx.errors.append(f"Output generation failed: {exc}")
            ctx.illustration_description = (
                f"[Fallback] {ctx.enriched_prompt} — rendered in {ctx.style} style, "
                f"with a {ctx.mood} mood using {ctx.color_palette} colour palette."
            )

        ctx.stage = "complete"
        return ctx


# ═══════════════════════════════════════════════════════
# Agent Orchestrator
# ═══════════════════════════════════════════════════════

class IllustrationAgent:
    """
    Top-level orchestrator that wires together all three stages.
    Initialises the Gemini SDK once and delegates to the pipeline.
    """

    def __init__(self) -> None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "GEMINI_API_KEY environment variable is required."
            )
        genai.configure(api_key=api_key)
        logger.info("[IllustrationAgent] Gemini SDK configured.")

        # Pipeline stages (ordered)
        self._pipeline = [
            InputHandler(),
            ReasoningStep(),
            OutputGenerator(),
        ]

    def run(
        self,
        prompt: str,
        style: Optional[str] = None,
        aspect_ratio: str = "16:9",
        detail_level: str = "detailed",
    ) -> AgentResult:
        """
        Execute the full agent pipeline and return a structured result.
        """
        ctx = AgentContext(
            raw_prompt=prompt,
            style=style,
            aspect_ratio=aspect_ratio,
            detail_level=detail_level,
        )

        # Run each stage sequentially
        for stage in self._pipeline:
            ctx = stage.run(ctx)
            if ctx.errors and ctx.stage == "init":
                break  # Abort early on hard validation errors

        elapsed_ms = int((time.time() - ctx.start_time) * 1000)
        ctx.metadata["processing_time_ms"] = elapsed_ms

        return AgentResult(
            success=len(ctx.errors) == 0 or bool(ctx.illustration_description),
            prompt=ctx.raw_prompt,
            illustration_description=ctx.illustration_description,
            style_tags=ctx.style_tags,
            mood=ctx.mood,
            color_palette=ctx.color_palette,
            suggested_tools=ctx.suggested_tools,
            metadata=ctx.metadata,
            processing_time_ms=elapsed_ms,
            errors=ctx.errors,
        )
