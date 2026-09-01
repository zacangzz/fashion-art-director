# Fashion AI Studio (Image Gen Pipeline)

> **Creative & Fashion AI Studio** — An enterprise-grade, deterministic creative studio and image generation pipeline that transforms moodboard imagery and artistic intent into reproducible, high-fidelity visual assets powered by Google GenAI multimodal models (`gemini-3.5-flash-lite`, `gemini-3.7-flash`, `gemini-3.1-flash-image`, `gemini-3-pro-image`).

---

## 🌐 Live Production Deployment

| Service | Endpoint URL | Description |
|---|---|---|
| **Production Web App** | [https://ai-art-director-prod.web.app](https://ai-art-director-prod.web.app) | Global Firebase Hosting CDN + Edge Routing |
| **Cloud Run Backend** | [https://fashion-art-director-1012864945903.asia-southeast1.run.app](https://fashion-art-director-1012864945903.asia-southeast1.run.app) | Auto-scaling FastAPI container service (`asia-southeast1`) |
| **Studio Observability** | [https://ai-art-director-prod.web.app/observability](https://ai-art-director-prod.web.app/observability) | Real-time audit logs, telemetry, cost tracking & DB explorer |
| **API Health Check** | [https://ai-art-director-prod.web.app/health](https://ai-art-director-prod.web.app/health) | Live service health check (`200 OK`) |

---

## 🚀 Key Capabilities

1. **5-Step Sequential Creative Workflow**:
   - **Step 1: Art Direction**: Upload 1–5 moodboard references + prompt to synthesize a 4-phase Master Prompt, 9-category visual levers, and 4 concurrent baseline candidate seeds (or skip via Direct Photo Ingestion).
   - **Step 2: Refinement**: Conversational natural-language chat studio with reference image conditioning, seed-locking, and interactive thread history timeline.
   - **Step 3: Canvas Studio**: Surgical spatial inpainting with full-canvas brush masking (`#FFFFFF` edit / `#000000` preserve), undo/redo stack, and boundary-preserving diffusion.
   - **Step 4: Wardrobe Studio**: Lookbook/sheet auto-detection and segmentation into categorized garment cards, interactive numbered pin-dropping (①, ②, ③) on subjects, and simultaneous multi-image composition.
   - **Step 5: Export Studio**: Lossless PNG / quality JPEG downloads, AI neural 4K master restoration & upscale, and 1-click 5-ratio production ZIP bundle (`4:5`, `9:16`, `1.85:1`, `1:1`, `1.8:1`) with JSON lineage metadata.

2. **Cloud-Native & Hybrid Architecture**:
   - **Google Cloud Storage (GCS)**: Scalable binary asset storage (`gs://ai-art-director-prod-store`) with automated CORS and secure HTTP 307 signed URL streaming.
   - **Cloud Firestore**: Serverless, multi-tenant NoSQL persistence across 7 flat collections with atomic batch writes and pre-computed lineage cost aggregation.
   - **Firebase Authentication**: Seamless Google OAuth and Email/Password authentication with automatic JWT Bearer token propagation.
   - **Secret Manager**: Secure API key management (`GEMINI_API_KEY`) accessed directly by Cloud Run runtime service accounts.

3. **Color Constancy & Chroma Preservation**:
   - Conditioning reference images are passed using lossless PNG/WebP with full ICC profile preservation to eliminate $\text{YUV 4:2:0}$ chroma degradation across iterative refinement turns.

4. **Automated CI/CD Pipeline (Keyless WIF)**:
   - Automated testing (Pytest + Vitest) and continuous deployment to Cloud Run & Firebase Hosting via GitHub Actions and **Workload Identity Federation (WIF)**.

---

## 5-Step Studio Workflow

```
[ Step 1: Art Direction ]
    │ Upload 1–5 reference images / PDFs + Prompt (or upload Direct Photo)
    │ AI extracts 9-category visual levers & synthesizes Master Prompt
    ▼ Concurrently generates 4 distinct baseline candidates
[ Step 2: Refinement Studio ]
    │ Select foundation baseline candidate
    │ Natural language conversational chat (lighting, mood, background)
    ▼ Seed-locked conditioning on parent image bytes
[ Step 3: Canvas Studio (Inpainting) ]
    │ Paint surgical binary mask over target region
    ▼ Natural language localized spot editing with boundary blending
[ Step 4: Wardrobe Studio (Styling) ]
    │ Auto-segment garment sheets into categorized cards
    │ Drag & drop numbered pins (①, ②, ③) onto subjects
    ▼ Multi-image composition conditioning simultaneously
[ Step 5: Export Studio (Production Delivery) ]
    │ Lossless PNG / configurable JPEG download
    │ AI neural 4K master upscale & restoration
    ▼ Download 1-click 5-Ratio ZIP Production Bundle
```

---

## 🛠️ Local Development Setup

### Prerequisites

- **Python 3.10+** (managed via [`uv`](https://docs.astral.sh/uv/))
- **Node.js 20+** and `npm`
- **Google AI Studio API Key** ([Get a key here](https://aistudio.google.com/app/apikey))

### Quickstart

#### 1. Configure Environment Variables
Create your local `.env` file:
```bash
cp .env.example .env
```
Edit `.env` and set your `GEMINI_API_KEY`:
```ini
GEMINI_API_KEY=your_actual_google_ai_studio_api_key_here
PORT=7860
HOST=127.0.0.1
DEBUG=True
STORAGE_DIR=./storage
VISION_MODEL=gemini-3.5-flash-lite
IMAGEN_MODEL=gemini-3.1-flash-image
INPAINT_MODEL=gemini-3-pro-image
```

#### 2. Start the Backend API Server
```bash
# Synchronize Python dependencies with uv
uv sync

# Launch FastAPI backend with hot reloading
uv run uvicorn src.app.main:app --host 127.0.0.1 --port 7860 --reload
```

#### 3. Start the Frontend Development Server
In a separate terminal:
```bash
cd src/frontend
npm install
npm run dev
```
Open **`http://localhost:5173`** in your browser.

---

## 🧪 Testing

### Backend Pytest Suite
Run the 79 backend tests covering services, Firestore management, pricing, and API endpoints:
```bash
uv run pytest
```

### Frontend Vitest Suite
Run the 104 frontend unit and component tests:
```bash
cd src/frontend
npm test
```

### Live Resiliency & Load Test
Run concurrency and latency benchmarks against the deployed production service:
```bash
python3 scripts/load_test.py
```

---

## 🚢 CI/CD & Deployment

Deployments are automated through GitHub Actions (`.github/workflows/deploy.yml`) using **Workload Identity Federation**:

1. Pushing to `main` executes unit and integration tests for both backend and frontend.
2. Once tests pass, the pipeline builds the multi-stage Docker container and deploys it to Cloud Run.
3. Firebase Hosting rules, indexes, and static assets are updated automatically.

### Manual Deployment via CLI

```bash
# 1. Deploy Cloud Run Backend
gcloud run deploy fashion-art-director \
  --project=ai-art-director-prod \
  --region=asia-southeast1 \
  --source=. \
  --service-account=studio-runner@ai-art-director-prod.iam.gserviceaccount.com \
  --set-secrets="GEMINI_API_KEY=GEMINI_API_KEY:latest" \
  --set-env-vars="GCP_PROJECT_ID=ai-art-director-prod,GCS_BUCKET=ai-art-director-prod-store,ENVIRONMENT=production" \
  --memory=2Gi \
  --cpu=2 \
  --timeout=300 \
  --allow-unauthenticated

# 2. Deploy Firebase Hosting
cd src/frontend && npm run build && cd ../..
npx -y firebase-tools deploy --project=ai-art-director-prod --only firestore:rules,firestore:indexes,hosting
```

---

## 📚 Documentation

- **[Product Requirements Document (PRD)](docs/PRD.md)**: Product vision, user journeys, 5-step workflow, and cloud architecture.
- **[Technical Specifications (SPEC)](docs/SPEC.md)**: Firestore schemas, REST API endpoints, multi-turn prompting architecture, and WIF CI/CD specification.
- **[Lessons Learned & API Insights](LESSONS.md)**: Resolution limits, color drift mitigation, structured outputs, and cloud configuration gotchas.
