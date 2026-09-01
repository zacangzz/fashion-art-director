# Technical Specification (SPEC)
## Image Gen Pipeline Studio

**Document Version**: 5.0  
**Status**: Active / 5-Step Production Studio Specification  
**Last Updated**: 2026-08-31  

---

## 1. System Architecture & High-Level Design

Image Gen Pipeline Studio is a full-stack local studio application comprising an asynchronous Python backend and a React SPA frontend.

```
┌────────────────────────────────────────────────────────────────────────────┐
│                             REACT SPA FRONTEND                             │
│  • App.jsx (5-Step Sequential Workflow Navigator & Global Studio State)    │
│  • Components: MoodboardUploader, PromptReviewSection, BaselineSelector,   │
│    RefinementChat, CanvasStudio, CanvasViewport, WardrobePanel,            │
│    ExportStudio, HistoryDrawer, ComparisonModal                            │
│  • Pages: ObservabilityPage (/telemetry & /observability)                  │
│  • Services: apiClient.js (HTTP client with X-Request-ID propagation)      │
└─────────────────────────────────────┬──────────────────────────────────────┘
                                      │ HTTP / REST & Static Assets
                                      ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                           FASTAPI BACKEND SERVICE                          │
│  • Routers: config, moodboard, generation, refinement, inpaint, wardrobe,  │
│    export, history, telemetry                                              │
│  • Middleware: CORS, Request Tracing (X-Request-ID), Structured Logging   │
│  • Static Mounts: /api/images (storage/generations), / (frontend SPA dist) │
└──────┬──────────────┬──────────────┬──────────────┬──────────────┬─────────┘
       │              │              │              │              │
       ▼              ▼              ▼              ▼              ▼
┌──────────────┐┌──────────────┐┌──────────────┐┌──────────────┐┌────────────┐
│Vision Service││Gen Service   ││Wardrobe Svc  ││Export Service││Telemetry & │
│• Flash Lite  ││• Flash/Pro   ││• Segmentation││• 4K Upscale  ││Cost Engine │
│• Master Extr ││  Image       ││• Pin Dropper ││• 5-Ratio ZIP ││• Pricing   │
│• 9-Taxonomy  ││• Seed Lock   ││• Multi-Part  ││• PIL Crop    ││• Auditing  │
└──────┬───────┘└──────┬───────┘└──────┬───────┘└──────┬───────┘└─────┬──────┘
       │               │               │               │              │
       ▼               ▼               ▼               ▼              ▼
┌──────────────────────────────────────────────┐┌────────────────────────────┐
│      GOOGLE GENAI INTERACTIONS API SDK       ││   LOCAL SQLITE & STORAGE   │
│ • gemini-3.5-flash-lite / gemini-3.7-flash   ││ • storage/studio.db        │
│ • gemini-3.1-flash-lite-image                ││ • storage/generations/     │
│ • gemini-3.1-flash-image / gemini-3-pro-image││ • storage/wardrobe/        │
│ • Structured JSON & Multi-Part Image Calling ││ • storage/logs/ (JSONL)    │
└──────────────────────────────────────────────┘└────────────────────────────┘
```

---

## 2. Data Models & Database Specifications

The persistence layer uses SQLite with `aiosqlite` located at `storage/studio.db`.

### 2.1 Database Tables & Schemas

#### 1. `moodboards`
Tracks moodboard ingestion batches, uploaded file paths, and upstream analysis costs.
```sql
CREATE TABLE IF NOT EXISTS moodboards (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    image_paths TEXT NOT NULL,           -- JSON array of file paths
    cost_usd REAL DEFAULT 0.0,
    tokens INTEGER DEFAULT 0,
    accumulated_cost_usd REAL DEFAULT 0.0,
    accumulated_tokens INTEGER DEFAULT 0
);
```

#### 2. `generations`
Stores every rendered image, seed, prompt, aspect ratio, resolution, model name, parent lineage pointer, and cost.
```sql
CREATE TABLE IF NOT EXISTS generations (
    id TEXT PRIMARY KEY,
    parent_id TEXT NULL,
    moodboard_id TEXT NULL,
    is_baseline BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    schema_json TEXT NOT NULL,           -- JSON payload (categories, narrative, inpaint_meta, etc.)
    compiled_prompt TEXT NOT NULL,
    negative_prompt TEXT,
    seed INTEGER NOT NULL,
    master_image_path TEXT NOT NULL,
    aspect_ratio TEXT NOT NULL DEFAULT '2:3',
    resolution_width INTEGER NOT NULL DEFAULT 1440,
    resolution_height INTEGER NOT NULL DEFAULT 1440,
    conversation_id TEXT NULL,
    model_name TEXT NULL,
    cost_usd REAL DEFAULT 0.0,
    tokens INTEGER DEFAULT 0,
    accumulated_cost_usd REAL DEFAULT 0.0,
    accumulated_tokens INTEGER DEFAULT 0,
    FOREIGN KEY(parent_id) REFERENCES generations(id),
    FOREIGN KEY(moodboard_id) REFERENCES moodboards(id)
);
```

#### 3. `conversations`
Tracks multi-turn refinement threads anchored to a root baseline generation.
```sql
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    baseline_generation_id TEXT NOT NULL,
    moodboard_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(baseline_generation_id) REFERENCES generations(id)
);
```

#### 4. `wardrobe_items`
Tracks segmented wardrobe pieces, bounding boxes, categories, and optional AI upscales.
```sql
CREATE TABLE IF NOT EXISTS wardrobe_items (
    id TEXT PRIMARY KEY,
    source_image_path TEXT NOT NULL,
    label TEXT NOT NULL,
    category TEXT DEFAULT 'tops',        -- outerwear, tops, bottoms, footwear, accessories, full_outfit
    cropped_image_path TEXT NOT NULL,
    upscaled_image_path TEXT NULL,
    upscale_status TEXT DEFAULT 'pending', -- pending, completed, failed
    upscale_error TEXT NULL,
    bbox_json TEXT,                      -- JSON array [ymin, xmin, ymax, xmax] (0-1000 scale)
    extracted_details_json TEXT NULL,    -- JSON object with fabric, colors, logos, text
    cost_usd REAL DEFAULT 0.0,
    tokens INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL
);
```

#### 5. `composition_assignments`
Records numbered pins dropped on viewport coordinates linking a generation to wardrobe library items.
```sql
CREATE TABLE IF NOT EXISTS composition_assignments (
    id TEXT PRIMARY KEY,
    generation_id TEXT NOT NULL,
    wardrobe_item_id TEXT NOT NULL,
    pin_number INTEGER NOT NULL,
    drop_position_json TEXT,             -- JSON object {"x": float, "y": float} (0.0 to 1.0)
    target_description TEXT,
    region_bbox_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(generation_id) REFERENCES generations(id),
    FOREIGN KEY(wardrobe_item_id) REFERENCES wardrobe_items(id)
);
```

---

## 3. REST API Contract & Endpoints Specification

### 3.1 Model Configuration
- **`GET /api/models/config`**
  - **Response**: `ModelConfigResponse`
    - `available_vision_models`: `["gemini-3.5-flash-lite", "gemini-3.7-flash"]`
    - `available_imagen_models`: `["gemini-3.1-flash-lite-image", "gemini-3.1-flash-image", "gemini-3-pro-image"]`
    - `default_vision_model`: string
    - `default_imagen_model`: string
    - `inpaint_model`: `"gemini-3-pro-image"`

### 3.2 Moodboard & Art Direction
- **`POST /api/moodboard/analyze-and-baselines`** *(Multipart Form)*
  - **Inputs**: `files` (1-5 files), `prompt` (str), `aspect_ratio` (str), `vision_model` (str), `imagen_model` (str)
  - **Process**: Performs vision extraction followed by 4 concurrent baseline image generations.
  - **Response**: `AnalyzeAndBaselinesResponse` (`moodboard_id`, `master_prompt`, `narrative`, `categories`, `baselines`, `conflicts`)

- **`POST /api/moodboard/analyze`** *(Multipart Form)*
  - **Inputs**: `files` (1-5 files), `prompt` (str), `locked_categories` (JSON str), `existing_categories` (JSON str), `aspect_ratio` (str), `vision_model` (str)
  - **Response**: `MoodboardAnalysisResponse` (`moodboard_id`, `master_prompt`, `narrative`, `categories`, `conflicts`, `extracted_chips`)

- **`POST /api/moodboard/generate-baselines`** *(JSON)*
  - **Inputs**: `GenerateBaselinesRequest` (`moodboard_id`, `master_prompt`, `categories`, `aspect_ratio`, `prompt_override`, `imagen_model`, `temperature`)
  - **Response**: `GenerateBaselinesResponse` (`moodboard_id`, `baselines: List[BaselineSummary]`)

- **`POST /api/moodboard/resync-prompt`** *(JSON)*
  - **Inputs**: `ResyncMasterPromptRequest` (`categories`, `narrative`, `previous_master_prompt`, `vision_model`)
  - **Response**: `ResyncMasterPromptResponse` (`master_prompt`, `narrative`, `categories`, `conflicts`)

- **`POST /api/moodboard/resync-levers`** *(JSON)*
  - **Inputs**: `ResyncLeversFromPromptRequest` (`master_prompt`, `narrative`, `categories`, `vision_model`)
  - **Response**: `ResyncLeversFromPromptResponse` (`categories`, `narrative`, `conflicts`)

- **`POST /api/moodboard/check-conflicts`** *(JSON)*
  - **Inputs**: `CheckConflictsRequest` (`master_prompt`, `narrative`, `categories`, `vision_model`)
  - **Response**: `CheckConflictsResponse` (`conflicts: List[PromptConflict]`)

- **`POST /api/moodboard/upload-direct-photo`** *(Multipart Form)*
  - **Inputs**: `file` (PNG/JPEG/WebP), `aspect_ratio` (optional str)
  - **Process**: Ingests user photo directly as a baseline record with auto-detected aspect ratio.
  - **Response**: `DirectPhotoUploadResponse` (`generation_id`, `image_url`, `seed`, `aspect_ratio`, `resolution`, `compiled_prompt`)

### 3.3 Refinement Studio
- **`POST /api/refine`** *(JSON)*
  - **Inputs**: `RefinementRequest` (`parent_id`, `prompt`, `seed`, `seed_mode`, `aspect_ratio`, `conversation_id`, `imagen_model`)
  - **Process**: Feeds parent master image bytes + relaxed refinement prompt wrapper to image model with seed lock.
  - **Response**: `RefinementResponse` (`generation_id`, `image_url`, `seed`, `compiled_prompt`, `aspect_ratio`, `resolution`, `conversation_id`, `cost_usd`, `accumulated_cost_usd`)

- **`GET /api/conversations/{conversation_id}`**
  - **Response**: `ConversationResponse` (`conversation_id`, `baseline_generation_id`, `messages: List[ConversationMessage]`)

### 3.4 Canvas Studio (Inpainting)
- **`POST /api/inpaint`** *(Multipart Form)*
  - **Inputs**: `image` (File), `mask` (File - B&W PNG), `prompt` (Form str), `generation_id` (Form str), `negative_prompt` (Form str), `seed` (int), `aspect_ratio` (str)
  - **Process**: Verifies mask coverage, encodes source image + mask bytes, applies strict boundary diffusion prompt wrapper.
  - **Response**: `InpaintResponse` (`generation_id`, `image_url`, `mask_url`, `mask_stats`, `seed`, `compiled_prompt`, `cost_usd`)

### 3.5 Wardrobe Studio
- **`POST /api/wardrobe/upload`** *(Multipart Form)*
  - **Inputs**: `file` (Image sheet), `vision_model` (str)
  - **Process**: Segments individual items via bounding boxes, crops images, saves records.
  - **Response**: `WardrobeUploadResponse` (`items: List[GarmentCard]`)

- **`GET /api/wardrobe/items`**
  - **Response**: `WardrobeListResponse` (`items: List[GarmentCard]`)

- **`DELETE /api/wardrobe/items/{item_id}`** & **`DELETE /api/wardrobe/items`**
  - **Response**: `{"status": "deleted", ...}`

- **`GET /api/wardrobe/items/{item_id}/image`** & **`GET /api/wardrobe/items/{item_id}/upscaled-image`**
  - **Response**: Image binary stream (`image/png`)

- **`POST /api/wardrobe/detect-regions`** *(JSON)*
  - **Inputs**: `DetectRegionsRequest` (`generation_id`, `vision_model`)
  - **Response**: `DetectRegionsResponse` (`regions: List[ClothingRegion]`)

- **`POST /api/wardrobe/compose`** *(JSON)*
  - **Inputs**: `WardrobeComposeRequest` (`parent_id`, `assignments: List[CompositionPinAssignment]`, `seed`, `conversation_id`, `custom_instruction`, `imagen_model`, `vision_model`)
  - **Process**: Multi-part Gemini Interactions request with parent image + all garment references.
  - **Response**: `WardrobeComposeResponse` (`generation_id`, `image_url`, `seed`, `compiled_prompt`, `assignments`, `cost_usd`, `accumulated_cost_usd`)

### 3.6 Export Studio & Bundling
- **`POST /api/export/prepare`** *(JSON)*
  - **Inputs**: `PrepareExportRequest` (`generation_id`, `prompt_override`)
  - **Process**: Executes AI neural restoration & 4K master upscale via Gemini image model.
  - **Response**: `PrepareExportResponse` (`generation_id`, `master_image_url`, `seed`, `compiled_prompt`, `resolution`)

- **`POST /api/export/bundle`** *(JSON)*
  - **Inputs**: `ExportBundleRequest` (`generation_id`)
  - **Process**: Crops/resizes master into 5 standard industry formats and packages into ZIP archive with lineage JSON.
  - **Response**: Binary `application/zip` download stream (`bundle_{generation_id}.zip`)

### 3.7 History & Lineage
- **`GET /api/history`**: Returns all generation records with lineage, schema snapshots, and costs.
- **`GET /api/generations/{generation_id}`**: Fetches single record.
- **`GET /api/generations/{generation_id}/lineage`**: Fetches root baseline, ancestor chain, and direct descendants.
- **`POST /api/generations/{generation_id}/restore`**: Restores studio workspace state.

### 3.8 Observability & Telemetry
- **`GET /api/telemetry/events`**: Paginated audit log search (filters: `component`, `event`, `request_id`, `status`, `search`).
- **`GET /api/telemetry/events/{request_id}`**: Full chronological lifecycle trace for a request ID.
- **`GET /api/telemetry/stats`**: Aggregated performance metrics, success rate, and average latencies.
- **`GET /api/telemetry/logs`**: Tail of `storage/logs/studio.log`.
- **`GET /api/telemetry/db/summary`**: SQLite row counts and column definitions.
- **`GET /api/telemetry/db/{table_name}`**: Paginated raw SQLite table inspector.

---

## 4. Multi-Turn Generative & Prompting Architecture

### 4.1 Gemini Interactions API Guidelines (`client.interactions.create`)

#### 1. Structured JSON Output Configuration
To request structured JSON output from Gemini models, always configure `type: "text"` with `mime_type: "application/json"`. Never use `{"type": "json"}` (which returns HTTP 400).
```python
interaction = client.interactions.create(
    model="gemini-3.5-flash-lite", # or gemini-3.7-flash
    input=input_content,
    system_instruction=system_instruction,
    response_format={
        "type": "text",
        "mime_type": "application/json",
    },
    generation_config={
        "temperature": 0.4,
    }
)
```

#### 2. Image Generation Configuration & Resolution Negotiation
```python
interaction = client.interactions.create(
    model="gemini-3-pro-image", # or gemini-3.1-flash-image, gemini-3.1-flash-lite-image
    input=input_items,
    response_format={
        "type": "image",
        "aspect_ratio": "16:9", # 1:1, 16:9, 9:16, 4:3, 3:4, 2:3, 3:2, etc.
        "image_size": "4K",     # 1K, 2K, 4K (4K/2K for Pro/Flash; 1K or omitted for Lite)
    },
    generation_config={
        "temperature": 1.0,
    }
)
```
*Resolution Rule*: `gemini-3.1-flash-lite-image` does not support `"2K"` or `"4K"` tiers and throws 404 if passed. The backend uses `resolve_model_image_size` to clamp Lite models to `"1K"` and Pro/Flash to `"4K"`.

### 4.2 Multi-Turn Chroma & Color Constancy Architecture

To prevent generational pixel degradation across multi-turn refinement and styling loops:
1. **Chroma Subsampling Mitigation**: Conditioning reference images are passed using **lossless PNG or lossless WebP** (`lossless=True`). Standard lossy JPEGs utilize $\text{YUV 4:2:0}$ subsampling which discards 75% of color information and shifts shadows over successive generations.
2. **ICC Profile Retention**: Embedded color profiles are extracted and preserved across all PIL transformations (`icc_profile=pil_img.info.get('icc_profile')`) to prevent wide-gamut (Display P3) saturation distortion.
3. **Color Constancy System Lock**: System prompts inject strict color temperature and white-balance directives, anchoring multi-turn styling ($\text{Turn} \ge 2$) to the root baseline scene chromaticity.

### 4.3 Prompting Taxonomy & Levers

Step 1 extracts descriptors across 9 visual dimensions:
1. `subject_details` (Subject & Character Details)
2. `objects_props` (Objects & Key Props)
3. `wardrobe_hair` (Wardrobe & Hairstyle)
4. `environment` (Environment & Setting)
5. `layout_framing` (Layout & Framing)
6. `lighting` (Lighting & Atmosphere)
7. `color_profile` (Color Profile & Palette)
8. `camera_optics` (Camera & Optical Specs)
9. `mood_era` (Mood, Vibe & Era)

The 4-Phase Master Prompt follows:
- **Phase 1: Creative Intent & Scene Context**
- **Phase 2: Subject & Detailed Styling**
- **Phase 3: Spatial Environment, Set Architecture & Props**
- **Phase 4: Lighting Physics & Optical Camera Specifications**

---

## 5. Wardrobe Auto-Segmentation & Pin Grounding

1. **Vision Auto-Detection**:
   - `wardrobe_service.segment_and_save_sheet` calls Gemini Vision with a structured bounding-box prompt.
   - Model returns normalized 2D boxes `[ymin, xmin, ymax, xmax]` on a `0–1000` integer grid.
2. **Cropping & Storage**:
   - PIL crops each detected region with safety padding and saves individual garment PNGs into `storage/wardrobe/items/`.
3. **Numbered Pin Placement (①, ②, ③)**:
   - Frontend records normalized drop coordinates `{"x": float, "y": float}` on the master canvas.
4. **Multi-Part Composition**:
   - Backend constructs a multi-part payload: `[Master Image Part, Garment 1 Part, Garment 2 Part, ..., Composition Prompt]`.
   - Prompt explicitly grounds each garment to its pin location and anatomical anchor.

---

## 6. Export Studio & Multi-Ratio Presets

The export engine formats the master image into standard production crops:

| Preset Name | Resolution | Ratio | Target Use Case |
|---|---|---|---|
| `01_SocialFeed_1080x1350` | $1080 \times 1350$ px | 4:5 | Instagram / Facebook Portrait Feed |
| `02_StoryMobile_1080x1920` | $1080 \times 1920$ px | 9:16 | Stories / TikTok / Mobile Fullscreen |
| `03_WideBanner_1440x780` | $1440 \times 780$ px | ~1.85:1 | Cinematic Web Hero / Wide Banner |
| `04_Square_1440x1440` | $1440 \times 1440$ px | 1:1 | High-Res E-Commerce Square |
| `05_LandscapeDisplay_1730x960` | $1730 \times 960$ px | ~1.8:1 | Editorial Display Landscape |
| `06_4KUHD_Landscape_3840x2160` | $3840 \times 2160$ px | 16:9 | 4K UHD Desktop & Television |
| `07_4KPortrait_2160x3840` | $2160 \times 3840$ px | 9:16 | 4K High-Res Poster / Digital Signage |
| `08_4KSquare_2160x2160` | $2160 \times 2160$ px | 1:1 | 4K Large Format Square Print |

All presets are packed with `lineage_metadata.json` into a single downloadable `.zip` archive.

---

## 7. Observability, Telemetry & Cost Engine

### 7.1 Structured JSONL Logs (`storage/logs/`)
- `studio.log`: Application log with log-level filtering and tailing.
- `generation_audit.jsonl`: Audit entries for baseline, refinement, inpainting, and export calls.
- `vision_audit.jsonl`: Audit entries for moodboard analysis, lever sync, and conflict checks.
- `wardrobe_audit.jsonl`: Audit entries for garment segmentation, detection, and composition.

### 7.2 Cost & Token Pricing Tiers
Calculated via `app/utils/pricing.py`:
- **Text & Vision Models**:
  - `gemini-3.5-flash-lite`: \$0.075 / 1M input tokens, \$0.30 / 1M output tokens.
  - `gemini-3.7-flash`: \$0.10 / 1M input tokens, \$0.40 / 1M output tokens.
- **Image Generation Models**:
  - `gemini-3.1-flash-lite-image`: \$0.020 per 1K image.
  - `gemini-3.1-flash-image`: \$0.030 per 1K image.
  - `gemini-3-pro-image`: \$0.040 per 1K image / \$0.080 per 4K image.
- **Lineage Cost Accumulation**:
  - Every child iteration recursively traces its ancestor chain to calculate `accumulated_cost_usd` and `accumulated_tokens`.

---

## 8. Directory & Storage Layout

```
image-gen-pipeline/
├── docs/
│   ├── PRD.md
│   ├── SPEC.md
│   └── prompting_architecture_and_data_flow_report.md
├── src/
│   ├── app/
│   │   ├── api/             # Routers: moodboard, refinement, inpaint, wardrobe, export, etc.
│   │   ├── db/              # DatabaseManager (SQLite with aiosqlite)
│   │   ├── prompts/         # Text templates & system prompts
│   │   ├── schemas/         # Pydantic models (domain.py)
│   │   ├── services/        # Vision, Generation, Wardrobe, Export, PromptCompiler
│   │   ├── utils/           # Image, JSON, Logger, Pricing, Telemetry
│   │   ├── config.py        # Pydantic Settings (.env validation & defaults)
│   │   ├── dependencies.py  # Service singletons & dependency injection
│   │   └── main.py          # FastAPI application & middleware
│   └── frontend/
│       ├── src/
│       │   ├── components/  # Studio React components (Canvas, Wardrobe, Chat, etc.)
│       │   ├── pages/       # ObservabilityPage (/telemetry)
│       │   ├── services/    # apiClient.js
│       │   ├── utils/       # Default tags, prompt compiler
│       │   ├── App.jsx      # Main application state & step workflow
│       │   └── index.css    # Modern Dark Studio styles
│       ├── dist/            # Compiled static SPA bundle
│       └── package.json
├── storage/
│   ├── studio.db            # SQLite database
│   ├── moodboards/          # Uploaded reference files
│   ├── generations/         # Rendered master PNGs
│   ├── wardrobe/            # Segmented garments & source sheets
│   └── logs/                # Audit logs & telemetry JSONL
├── launch.command           # Desktop zero-setup launcher
└── pyproject.toml           # Python dependencies managed with uv
```
