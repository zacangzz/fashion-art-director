# Image Gen Pipeline Studio

> **Version 2.0** — Image generation pipeline built on a sparse JSON Scene Schema, interactive visual graph canvas, seed-locked continuity, lineage history, and 4K multi-ratio delivery.

---

## Key Features

1. **Sparse JSON Scene Schema**:
   Always includes `schema_version`, `metadata`, `canvas`, `creative_direction`, and `style`; other populated scene sections are optional.

2. **Automated Inception & 4-Baseline Generation**:
   Upload 1–5 reference images or PDFs. Gemini 3.1 Flash Lite automatically synthesizes the Master JSON Scene Schema and immediately generates **4 concurrent baseline image candidates** across distinct random seeds.

3. **JSON Crack-Inspired Visual Graph Canvas & Inspector**:
   Interactive node-graph editor with pan, zoom, search filtering, and dynamic SVG Bezier connector lines. Fine-tune parameters with inline micro-controls (color swatches, numerical scrubbers, preset dropdowns) or deep slide-out property inspector.

4. **Seed-Locked Multimodal Continuity**:
   Re-generate artwork without generational pixel loss. Locks the chosen baseline seed and passes the baseline image as reference conditioning alongside JSON parameter deltas.

5. **Phase 4 Capabilities**:
   - **Lineage History Drawer**: Chronological tree tracking root baselines and fine-tuned child iterations with 1-click studio state restore.
   - **Split-Slider Diff Modal**: Fullscreen comparison modal with interactive split-slider widget and JSON parameter diff table.
   - **4K Multi-Ratio Bundle Exporter**: 1-click ZIP export generating 5 standard production ratios (`1080x1350`, `1080x1920`, `1440x780`, `1440x1440`, `1730x960`) via Pillow Lanczos resampling.
   - **macOS Desktop Launcher**: Zero-setup double-click `launch.command` script.

---

## Getting Started

### Prerequisites
- Python 3.10+ (or [uv](https://docs.astral.sh/uv/))
- Node.js 18+ & npm
- Google AI Studio API Key (`GEMINI_API_KEY`)

### Quick Start (macOS Double-Click)
Double-click `./launch.command` or run:
```bash
./launch.command
```

### Manual Setup
1. **Backend**:
   ```bash
   uv sync
   source .venv/bin/activate
   cp .env.example .env # Configure your GEMINI_API_KEY
   uvicorn --app-dir src app.main:app --port 7860 --reload
   ```

2. **Frontend**:
   ```bash
   cd src/frontend
   npm install
   npm run dev
   ```

Open your browser to `http://localhost:5173` (or `http://localhost:7860`).

---

## 3-Step Studio Workflow

```
[ Step 1: Moodboard & Baselines ]
    │ Upload 1–5 reference images / PDFs
    │ AI extracts a sparse JSON Scene Schema
    ▼ Concurrently generates 4 distinct baseline candidates
[ Step 2: Visual Graph Studio & Inspector ]
    │ Select your foundation baseline
    │ Pan & zoom visual node canvas, tweak inline swatches/sliders
    ▼ Edit the canonical JSON scene specification
[ Step 3: Seed-Locked Fine-Tuning & 4K Export ]
    │ Fine-tune parameters with seed-locking & image reference
    │ Trace lineage in History Drawer & compare versions in Split Diff
    ▼ Download 1-click 5-Preset ZIP Bundle
```

---

## Test Suite

- **Backend Pytest Suite**:
  ```bash
  .venv/bin/pytest -v
  ```
- **Frontend Vitest Suite**:
  ```bash
  cd src/frontend && npm test
  ```
