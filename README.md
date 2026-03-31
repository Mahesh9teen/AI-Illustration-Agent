# 🎨 AI Illustration Agent

> An ADK-based AI agent that transforms text prompts into rich, production-ready illustration descriptions using Google Gemini — deployable on Google Cloud Run.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture](#architecture)
3. [Project Structure](#project-structure)
4. [Local Setup](#local-setup)
5. [API Usage](#api-usage)
6. [Docker Build & Run](#docker-build--run)
7. [Deploy to Google Cloud Run](#deploy-to-google-cloud-run)
8. [Environment Variables](#environment-variables)
9. [Sample Request / Response](#sample-request--response)
10. [Extending the Agent](#extending-the-agent)

---

## Project Overview

The **AI Illustration Agent** accepts a plain-English description and returns a
rich, detailed illustration specification ready to be fed into any image
generation service (Google Imagen 3, DALL-E 3, Midjourney, Stable Diffusion XL,
etc.).

The agent runs a **three-stage ADK pipeline**:

| Stage | Class | Responsibility |
|-------|-------|----------------|
| 1 | `InputHandler` | Validate, sanitise, and normalise the user prompt |
| 2 | `ReasoningStep` | Infer art style, mood, colour palette via Gemini |
| 3 | `OutputGenerator` | Generate the final vivid illustration description |

---

## Architecture

```
User → POST /generate
            │
            ▼
      ┌─────────────┐
      │ InputHandler│  ← validates prompt, normalises style
      └──────┬──────┘
             │  AgentContext
             ▼
      ┌──────────────┐
      │ReasoningStep │  ← Gemini call → style tags, mood, palette
      └──────┬───────┘
             │  enriched spec
             ▼
      ┌────────────────┐
      │OutputGenerator │  ← Gemini call → vivid illustration description
      └──────┬─────────┘
             │  AgentResult
             ▼
      JSON Response (FastAPI)
```

---

## Project Structure

```
ai-illustration-agent/
├── app/
│   ├── main.py       # FastAPI app factory, startup/shutdown events
│   ├── agent.py      # ADK agent pipeline (InputHandler, ReasoningStep, OutputGenerator)
│   ├── routes.py     # HTTP endpoints: GET / and POST /generate
│   └── utils.py      # Shared helpers: sanitisation, JSON parsing, timing
├── Dockerfile        # Multi-stage Docker build (builder + runtime)
├── requirements.txt  # Pinned Python dependencies
└── README.md         # This file
```

---

## Local Setup

### Prerequisites

- Python 3.11+
- A **Google Gemini API key** ([get one here](https://makersuite.google.com/app/apikey))

### Steps

```bash
# 1. Clone the repo
git clone https://github.com/your-org/ai-illustration-agent.git
cd ai-illustration-agent

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set your Gemini API key
export GEMINI_API_KEY="your-api-key-here"

# 5. Start the server
cd app
uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

Visit **http://localhost:8080/docs** for the interactive Swagger UI.

---

## API Usage

### `GET /`  — Health Check

```bash
curl http://localhost:8080/
```

```json
{
  "status": "ok",
  "version": "1.0.0",
  "gemini_configured": true,
  "timestamp": 1720000000.123
}
```

---

### `POST /generate`  — Generate Illustration

**Request body:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `prompt` | string | ✅ | — | Text description (3–1000 chars) |
| `style` | string | ❌ | auto | Art style (see supported list) |
| `aspect_ratio` | string | ❌ | `16:9` | One of: `16:9`, `9:16`, `1:1`, `4:3`, `3:4`, `21:9` |
| `detail_level` | string | ❌ | `detailed` | `simple` \| `moderate` \| `detailed` |

**Supported styles:**
`watercolor`, `oil_painting`, `pencil_sketch`, `digital_art`, `anime`,
`photorealistic`, `impressionist`, `minimalist`, `concept_art`, `comic_book`,
`pixel_art`, `surrealism`

---

## Docker Build & Run

```bash
# Build the image
docker build -t ai-illustration-agent:latest .

# Run locally with your API key
docker run -p 8080:8080 \
  -e GEMINI_API_KEY="your-api-key-here" \
  ai-illustration-agent:latest

# Test it
curl http://localhost:8080/
```

---

## Deploy to Google Cloud Run

### Prerequisites

- [gcloud CLI](https://cloud.google.com/sdk/docs/install) installed and authenticated
- A GCP project with billing enabled
- Cloud Run API and Artifact Registry API enabled

### Step-by-step

```bash
# ── 1. Set your project variables ──────────────────────────────────────────
export PROJECT_ID="your-gcp-project-id"
export REGION="us-central1"
export SERVICE_NAME="ai-illustration-agent"
export REPO_NAME="illustration-agent-repo"
export IMAGE="$REGION-docker.pkg.dev/$PROJECT_ID/$REPO_NAME/$SERVICE_NAME"

# ── 2. Authenticate Docker with GCP ────────────────────────────────────────
gcloud auth configure-docker $REGION-docker.pkg.dev

# ── 3. Create an Artifact Registry repository (one-time) ───────────────────
gcloud artifacts repositories create $REPO_NAME \
  --repository-format=docker \
  --location=$REGION \
  --description="AI Illustration Agent images"

# ── 4. Build and tag the Docker image ──────────────────────────────────────
docker build --platform linux/amd64 -t $IMAGE:latest .

# ── 5. Push to Artifact Registry ───────────────────────────────────────────
docker push $IMAGE:latest

# ── 6. Store the Gemini API key in Secret Manager (recommended) ────────────
echo -n "your-api-key-here" | \
  gcloud secrets create GEMINI_API_KEY --data-file=- \
  --replication-policy=automatic

# ── 7. Deploy to Cloud Run ─────────────────────────────────────────────────
gcloud run deploy $SERVICE_NAME \
  --image=$IMAGE:latest \
  --platform=managed \
  --region=$REGION \
  --allow-unauthenticated \
  --port=8080 \
  --memory=1Gi \
  --cpu=1 \
  --min-instances=0 \
  --max-instances=10 \
  --set-secrets="GEMINI_API_KEY=GEMINI_API_KEY:latest"

# ── 8. Get the service URL ─────────────────────────────────────────────────
gcloud run services describe $SERVICE_NAME \
  --region=$REGION \
  --format="value(status.url)"
```

### CI/CD with Cloud Build (optional)

Add a `cloudbuild.yaml` to automate the build → push → deploy pipeline:

```yaml
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '--platform', 'linux/amd64', '-t', '$_IMAGE', '.']
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', '$_IMAGE']
  - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    args:
      - gcloud
      - run
      - deploy
      - ai-illustration-agent
      - --image=$_IMAGE
      - --region=us-central1
      - --platform=managed
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | ✅ | Your Google Gemini API key |
| `PORT` | ❌ | Port to listen on (default: `8080`). Set automatically by Cloud Run. |

---

## Sample Request / Response

### Request

```bash
curl -X POST https://<your-cloud-run-url>/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "A lone samurai standing on a cliff at sunset, cherry blossoms falling around him",
    "style": "watercolor",
    "aspect_ratio": "16:9",
    "detail_level": "detailed"
  }'
```

### Response

```json
{
  "success": true,
  "prompt": "A lone samurai standing on a cliff at sunset, cherry blossoms falling around him",
  "illustration_description": "A solitary samurai warrior stands in proud silhouette upon a weathered granite cliff edge, his worn haori cloak billowing gently in the warm evening wind. The sky behind him explodes in a symphony of burnt amber, rose gold, and deep vermilion as the sun descends toward a mist-wrapped mountain horizon. A cascade of pale pink cherry blossoms spirals gracefully around the figure, each petal catching the dying light like scattered embers. Rendered in luminous watercolor with deliberate wet-on-wet bleeds, the composition balances exquisite softness in the background with crisp ink line-work defining the samurai's armour and katana. The palette flows from cool lavender in the upper sky through fiery orange mid-tones to deep indigo shadows pooling at the cliff base. The overall mood is one of serene melancholy — a warrior at peace between worlds, framed by nature's ephemeral beauty.",
  "style_tags": ["feudal Japan", "samurai", "cherry blossom", "sunset", "silhouette"],
  "mood": "melancholic",
  "color_palette": "burnt amber, rose gold, vermilion, lavender, pale pink",
  "suggested_tools": [
    "Google Imagen 3",
    "Stable Diffusion XL",
    "DALL-E 3",
    "Midjourney v6"
  ],
  "metadata": {
    "input_length": 80,
    "style_requested": "watercolor",
    "aspect_ratio": "16:9",
    "detail_level": "detailed",
    "reasoning_style_used": "watercolor",
    "processing_time_ms": 2341
  },
  "processing_time_ms": 2341,
  "errors": []
}
```

---

## Extending the Agent

The pipeline is fully modular. To add a new stage:

1. Create a class with a `run(self, ctx: AgentContext) -> AgentContext` method.
2. Add it to the `self._pipeline` list inside `IllustrationAgent.__init__`.

**Example — add a content moderation stage:**

```python
class ModerationStep:
    def run(self, ctx: AgentContext) -> AgentContext:
        if is_unsafe(ctx.raw_prompt):
            ctx.errors.append("Prompt violates content policy.")
        return ctx
```

```python
# In IllustrationAgent.__init__:
self._pipeline = [
    InputHandler(),
    ModerationStep(),   # ← insert anywhere
    ReasoningStep(),
    OutputGenerator(),
]
```

---

## License

MIT © 2024 Your Organisation
#   A I - I l l u s t r a t i o n - A g e n t  
 