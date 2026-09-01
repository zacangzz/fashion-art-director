# Image Gen Pipeline Studio

> **Creative & Fashion AI Studio** — A self-contained local studio that transforms moodboard imagery and creative intent into reproducible, deterministic, and fine-grain controllable image generation workflows powered by Google GenAI multimodal models.

---

## Key Capabilities

1. **5-Step Sequential Creative Workflow**:
   - **Step 1: Art Direction**: Upload 1–5 moodboard references + creative prompt to synthesize an optimal 4-phase Master Prompt, 9-category visual levers, and 4 concurrent baseline candidate seeds (or skip via Direct Photo Ingestion).
   - **Step 2: Refinement**: Conversational natural-language chat studio with reference image conditioning, seed-locking, and interactive thread history timeline.
   - **Step 3: Canvas Studio**: Surgical spatial inpainting with full-canvas brush masking (`#FFFFFF` edit / `#000000` preserve), undo/redo stack, and boundary-preserving diffusion.
   - **Step 4: Wardrobe Studio**: Lookbook/sheet auto-detection and segmentation into categorized garment cards, interactive numbered pin-dropping (①, ②, ③) on subjects, and simultaneous multi-image composition.
   - **Step 5: Export Studio**: Lossless PNG / quality JPEG downloads, AI neural 4K master restoration & upscale, and 1-click 5-ratio production ZIP bundle (`4:5`, `9:16`, `1.85:1`, `1:1`, `1.8:1`) with JSON lineage metadata.

2. **Chroma & Color Constancy Architecture**:
   - Multi-turn reference conditioning encoded in lossless PNG/WebP with ICC profile preservation to eliminate $\text{YUV 4:2:0}$ chroma subsampling degradation and color drift across iterations.

3. **Observability & Telemetry Subsystem**:
   - Built-in Observability Dashboard (`/telemetry` & `/observability`) with real-time audit logs, request lifecycle tracing (`req_...`), latency metrics, token/cost engine, and raw SQLite table inspector.

4. **100% Local Data Sovereignty**:
   - All database records (`storage/studio.db`), generated images (`storage/generations/`), wardrobe pieces (`storage/wardrobe/`), and audit trails (`storage/logs/`) reside locally on your machine.

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

## Prerequisites

- **Python 3.10+** (managed via [`uv`](https://docs.astral.sh/uv/))
- **Node.js 18+** and `npm`
- **Google AI Studio API Key** ([Get a key here](https://aistudio.google.com/app/apikey))

---

## How to Run the App

### Option A: One-Click Desktop Launcher (macOS)

The repository includes an automated launcher script that verifies dependencies, syncs the Python virtual environment with `uv`, validates your `.env` key, builds frontend assets if needed, frees ports, starts the backend, and opens your browser:

```bash
./launch.command
```

*(You can also double-click `launch.command` in macOS Finder).*

---

### Option B: Manual Setup & Execution

#### 1. Configure Environment Variables
Create your local `.env` file from the provided template:
```bash
cp .env.example .env
```
Edit `.env` and set your `GEMINI_API_KEY`:
```ini
GEMINI_API_KEY=your_actual_google_ai_studio_api_key_here
PORT=7860
HOST=127.0.0.1
DEBUG=True
DATABASE_URL=sqlite:///./storage/studio.db
STORAGE_DIR=./storage
VISION_MODEL=gemini-3.5-flash-lite
IMAGEN_MODEL=gemini-3.1-flash-image
INPAINT_MODEL=gemini-3-pro-image
```

#### 2. Start the Backend API Server
Use `uv` to synchronize dependencies and start the Uvicorn ASGI server:
```bash
# Synchronize locked dependencies
uv sync

# Activate virtual environment
source .venv/bin/activate

# Launch FastAPI backend on port 7860
uvicorn --app-dir src app.main:app --host 127.0.0.1 --port 7860 --reload
```

#### 3. Launch the Frontend Studio

##### Development Mode (Hot Reloading — Recommended for development):
In a separate terminal window:
```bash
cd src/frontend
npm install
npm run dev
```
Open your browser to: **`http://localhost:5173`**

##### Production Mode (Served directly by FastAPI backend):
Build the static bundle once:
```bash
cd src/frontend
npm install
npm run build
```
Open your browser directly to: **`http://localhost:7860`**

---

## Observability & Telemetry

Open the built-in Observability & Telemetry Dashboard to monitor live operations, audit logs, model costs, and database records:
- **Dev URL**: `http://localhost:5173/telemetry`
- **Backend / Production URL**: `http://localhost:7860/telemetry`
- **Interactive API Documentation (Swagger)**: `http://localhost:7860/docs`
- **Backend Health Check**: `http://localhost:7860/health`

---

## Configuration Reference (`.env`)

| Variable | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | *None* | Google AI Studio API Key (**Required**) |
| `PORT` | `7860` | Port for the backend FastAPI server |
| `HOST` | `127.0.0.1` | Host address for binding |
| `VISION_MODEL` | `gemini-3.5-flash-lite` | Default Vision Director model (`gemini-3.5-flash-lite`, `gemini-3.7-flash`) |
| `IMAGEN_MODEL` | `gemini-3.1-flash-image` | Default Image Generation model (`gemini-3.1-flash-lite-image`, `gemini-3.1-flash-image`, `gemini-3-pro-image`) |
| `INPAINT_MODEL` | `gemini-3-pro-image` | Model for Canvas spatial inpainting |
| `DATABASE_URL` | `sqlite:///./storage/studio.db` | SQLite database URI |
| `STORAGE_DIR` | `./storage` | Local directory for images, masks, and logs |
| `GENAI_TIMEOUT_SECONDS` | `300` | Timeout threshold for Google GenAI API calls |

---

## Running the Test Suites

### Backend Pytest Suite
Run the 106+ backend unit and integration tests covering services, database migrations, conflict scans, pricing, and API endpoints:
```bash
.venv/bin/pytest -v
```

### Frontend Vitest Suite
Run the 104+ component and client tests:
```bash
cd src/frontend
npm test -- --run
```

---

## Documentation

- **[Product Requirements Document (PRD)](docs/PRD.md)**: Product vision, user journeys, 5-step workflow, and functional requirements.
- **[Technical Specifications (SPEC)](docs/SPEC.md)**: System architecture, SQLite schemas, REST API endpoints, multi-turn prompting architecture, wardrobe pin grounding, and observability engine.
- **[Prompting Architecture & Data Flow](docs/prompting_architecture_and_data_flow_report.md)**: Deep dive into Gemini vision synthesis, prompt compiler, relaxed refinement directives, and spatial inpaint prompt wrappers.
