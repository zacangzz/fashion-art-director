# Comprehensive Prompt & API Payload Registry

This document provides an exhaustive, production-accurate, verbatim reference of **every prompt, system directive, user template, dynamic compiler, and multimodal API payload** transmitted to Google GenAI / Gemini / Imagen APIs across every stage of the application lifecycle.

---

## 1. Lifecycle Overview & Master Prompt Matrix

The application operates across a **4-Step Sequential Studio Architecture** with auxiliary specialized modules for Wardrobe Styling, Subject Grounding, Auto-Mask Region Detection, and AI Master Upscaling:

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Step 1: Art Direction & Moodboard Synthesis                                                      │
│ ├─ 1A. Visual Levers & Master Prompt Extraction (extraction_system.txt + user_baseline_template) │
│ ├─ 1B. Re-sync Master Prompt from Visual Levers (resync_master_prompt_system.txt + template)      │
│ ├─ 1C. Concurrent 4-Candidate Baseline Generation (Master Prompt / compile_prompt + suffix)     │
│ └─ 1D. Direct User Photo Ingestion (Aspect-ratio auto-detection & baseline registration)         │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
                                                │
                                                ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Step 2: Iterative Refinement & Wardrobe Studio                                                   │
│ ├─ 2A. Conversational Natural Language Refinement (refinement_system.txt + parent image)         │
│ ├─ 2B. Seed-Locked Fine-Tuning with Tag Delta Compiler (compile_delta_prompt + parent image)      │
│ ├─ 2C. Wardrobe Lookbook Sheet Auto-Segmentation (wardrobe_segmentation.txt + sheet image)       │
│ ├─ 2D. Vision Subject Grounding Pre-Pass (subject_grounding_system.txt + pin coordinates)       │
│ ├─ 2E. Multi-Garment Wardrobe Composition (wardrobe_composition_system.txt + N garment images)   │
│ └─ 2F. Clothing Region Detection for Auto-Masking (clothing_region_detection.txt + scene image)  │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
                                                │
                                                ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Step 3: Canvas Studio (Spatial Inpainting)                                                       │
│ └─ Targeted Spatial Inpainting (inpaint_system.txt + inpaint_suffix.txt + source & mask images)   │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
                                                │
                                                ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Step 4: Export Studio & AI Master Restoration                                                    │
│ └─ AI Master 4K Raw Photo Restoration (DEFAULT_UPSCALE_PROMPT + parent image + seed lock)        │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Master Prompt & API Payload Inventory

| # | Step / Workflow Action | Source Files | Target API & Default Model | Input Contents Structure (Wire Payload) | Output Schema / Modality |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **1A** | **Moodboard & Intent Extraction** | `src/app/prompts/extraction_system.txt`<br>`src/app/prompts/user_baseline_template.txt` | `generate_content`<br>`gemini-3.5-flash-lite` | `system_instruction`: `EXTRACTION_SYSTEM_PROMPT`<br>`contents`: `[ImagePart(1..5), USER_BASELINE_TEMPLATE]` | Structured JSON (`application/json`): `master_prompt`, `narrative`, 9-category visual levers |
| **1B** | **Re-sync Master Prompt** | `src/app/prompts/resync_master_prompt_system.txt`<br>`src/app/prompts/resync_master_prompt_template.txt` | `generate_content`<br>`gemini-3.5-flash-lite` | `system_instruction`: `RESYNC_MASTER_PROMPT_SYSTEM`<br>`contents`: `[RESYNC_MASTER_PROMPT_TEMPLATE]` | Structured JSON: updated `master_prompt`, `narrative` |
| **1C** | **4-Candidate Baseline Generation** | `src/app/prompts/image_generation_suffix.txt`<br>`src/app/prompts/defaults.json`<br>`src/app/services/generation_service.py` | `generate_content` / `generate_images`<br>`gemini-3-pro-image` / `imagen` | Gemini: `contents = [f"{master_prompt} {suffix}"]`<br>Imagen: `prompt = master_prompt`, `config = GenerateImagesConfig` | Image bytes (4 parallel calls across 4 distinct random seeds) |
| **1D** | **Direct Photo Upload Baseline** | `src/app/services/generation_service.py` | N/A (Direct Registration) | Analyzes local image dimensions, detects aspect ratio, embeds 600 DPI, stores baseline DB record | Direct Image URL + baseline generation ID |
| **2A** | **Conversational Refinement** | `src/app/prompts/refinement_system.txt`<br>`src/app/prompts/image_generation_suffix.txt` | `generate_content`<br>`gemini-3-pro-image` | `contents = [ImagePart(parent_bytes), f"{REFINEMENT_SYSTEM_PROMPT} {suffix}"]` | Single refined image bytes with seed lock |
| **2B** | **Tag Delta Fine-Tuning** | `src/app/services/generation_service.py`<br>`src/frontend/src/utils/promptCompiler.js` | `generate_content`<br>`gemini-3-pro-image` | `contents = [ImagePart(parent_bytes), f"{compile_delta_prompt()} {suffix}"]` | Single fine-tuned image bytes with locked category anchors |
| **2C** | **Wardrobe Sheet Segmentation** | `src/app/prompts/wardrobe_segmentation.txt` | `generate_content`<br>`gemini-3.5-flash-lite` | `contents = [ImagePart(sheet_bytes), WARDROBE_SEGMENTATION_PROMPT]`<br>`config`: `temperature=0.0`, `response_schema=WardrobeSegmentationResult` | JSON array of detected garments with label, category, and `[ymin, xmin, ymax, xmax]` 0..1000 |
| **2D** | **Vision Subject Grounding Pre-Pass** | `src/app/prompts/subject_grounding_system.txt`<br>`src/app/services/wardrobe_service.py` | `generate_content`<br>`gemini-3.5-flash-lite` | `contents = [ImagePart(parent_bytes), pin_text, SUBJECT_GROUNDING_PROMPT]` | JSON object: `grounded_pins` (subject, body location, attire) + non-target guardrail |
| **2E** | **Multi-Garment Wardrobe Composition** | `src/app/prompts/wardrobe_composition_system.txt`<br>`src/app/services/generation_service.py` | `generate_content`<br>`gemini-3-pro-image` | Multi-image contents array:<br>`[ImagePart(parent), "Base Scene...", "Garment #1:", ImagePart(g1), ..., WARDROBE_COMPOSITION_PROMPT, suffix]` | Single composited image bytes with garment transfer & multi-subject invariance |
| **2F** | **Clothing Region Detection (Auto-Mask)** | `src/app/prompts/clothing_region_detection.txt` | `generate_content`<br>`gemini-3.5-flash-lite` | `contents = [ImagePart(scene_bytes), CLOTHING_REGION_DETECTION_PROMPT]`<br>`config`: `response_schema=ClothingRegionDetectionResult` | JSON array of clothing regions with normalized float bboxes for interactive canvas overlay |
| **3** | **Canvas Studio Spatial Inpainting** | `src/app/prompts/inpaint_system.txt`<br>`src/app/prompts/inpaint_suffix.txt` | `generate_content`<br>`gemini-3-pro-image` | `contents = [PIL.Image(base), PIL.Image(mask), f"{INPAINT_SYSTEM_PROMPT}\n\n{INPAINT_SUFFIX}"]`<br>`config`: `response_modalities=["IMAGE", "TEXT"]` | Single inpainted image bytes strictly preserving pixels outside white mask |
| **4** | **Export Master AI Restoration** | `src/app/services/export_service.py` (`DEFAULT_UPSCALE_PROMPT`) | `generate_content`<br>`gemini-3-pro-image` | `contents = [ImagePart(source_bytes), f"{DEFAULT_UPSCALE_PROMPT} {suffix}"]` | Enhanced 4K master image bytes with 600 DPI optical definition & fabric micro-texture |

---

## 2. Model Selection & Configuration Architecture

The platform supports dynamic, user-selected Google GenAI models configurable via `.env`, the `/api/models/config` endpoint, and UI dropdown selectors:

* **Available Vision Models**:
  - `gemini-3.5-flash-lite` (Default: ultra-fast multimodal reasoning, tag extraction, segmentation, and subject grounding)
  - `gemini-3.7-flash` (Advanced visual reasoning and complex character disambiguation)
* **Available Image Generation / Editing Models**:
  - `gemini-3-pro-image` (Default: state-of-the-art multimodal image generation, reference conditioning, and multi-image composition)
  - `gemini-3.1-flash-image` (High-speed multimodal image generation & inpainting)
  - `gemini-3.1-flash-lite-image` (Lightweight generation)
  - `imagen-3.0-capability-001` (Legacy text-to-image pipeline via `client.models.generate_images`)
* **Dedicated Inpainting Model**: `gemini-3-pro-image` (Fixed high-precision spatial inpainting).

---

## 3. Step 1: Art Direction & Moodboard Synthesis

### 3.1. Step 1A: Visual Levers & Master Prompt Extraction

When the user uploads 1–5 moodboard reference images along with an optional starting creative direction, `VisionService.extract_tag_studio_state` analyzes the visual context and extracts the Master Prompt, scene narrative, and 9-category visual levers.

* **API Method**: `client.models.generate_content` (or `client.aio.models.generate_content`)
* **Target Model**: `gemini-3.5-flash-lite` (or user-selected `gemini-3.7-flash`)
* **Configuration**: `types.GenerateContentConfig(response_mime_type="application/json", system_instruction=EXTRACTION_SYSTEM_PROMPT)`
* **Source Files**: `src/app/prompts/extraction_system.txt`, `src/app/prompts/user_baseline_template.txt`

#### Wire Payload Structure Sent to API:
```python
contents = [
    to_image_part(moodboard_bytes_1),
    to_image_part(moodboard_bytes_2),
    # ... up to 5 moodboard images
    USER_BASELINE_TEMPLATE.replace("{USER_PROMPT}", user_prompt.strip())  # (appended if user provided text)
]
```

#### Verbatim System Prompt (`extraction_system.txt`):
```text
You are an executive visual director, master cinematographer, and elite image generation prompt architect.
Your mission is to analyze the reference moodboard images and user creative requirements, then synthesize the OPTIMAL, highest-fidelity generation prompt alongside its constituent visual levers.

You must return a single, valid JSON object with EXACTLY this structure:
{
  "master_prompt": "A complete, highly polished, evocative Master Generation Prompt designed to produce the definitive image matching the moodboard and requirements. Synthesize the scene, subject, wardrobe, environment, lighting, optics, color profile, and artistic aesthetic into a cohesive, cinematic description.",
  "narrative": "A concise 1-2 sentence core creative scene logline capturing the primary subject, action, setting, and emotional tone.",
  "categories": {
    "subject_details": [
      {"label": "<specific visual descriptor inferred from moodboard>"}
    ],
    "objects_props": [
      {"label": "<specific visual descriptor inferred from moodboard>"}
    ],
    "wardrobe_hair": [
      {"label": "<specific visual descriptor inferred from moodboard>"}
    ],
    "environment": [
      {"label": "<specific visual descriptor inferred from moodboard>"}
    ],
    "layout_framing": [
      {"label": "<specific visual descriptor inferred from moodboard>"}
    ],
    "lighting": [
      {"label": "<specific visual descriptor inferred from moodboard>"}
    ],
    "color_profile": [
      {"label": "<specific visual descriptor inferred from moodboard>"}
    ],
    "camera_optics": [
      {"label": "<specific visual descriptor inferred from moodboard>"}
    ],
    "mood_era": [
      {"label": "<specific visual descriptor inferred from moodboard>"}
    ]
  }
}

Directives:
1. MASTER PROMPT EXCELLENCE: The `master_prompt` must be rich, concrete, evocative, and free of vague synthetic buzzwords. Strictly NEVER use "photorealistic", "photorealism", "hyperrealistic", or "4K". Instead, prioritize authentic analog cues ("raw photo", "subtle dust and scratches", "visible skin pores", "natural skin texture", "realistic teeth texture", "natural tooth alignment", "authentic gum line", "subtle dental translucency", "minor skin blemishes", "slight motion blur", "natural light"), specific camera optics with exact numeric aperture stops (such as 35mm f/1.4, 50mm f/1.8, 85mm f/1.4, f/2.8, f/4, f/8) to dictate depth and optical rendering instead of vague generic phrases like "shallow depth of field", realistic lighting behavior, physical materials, and atmospheric depth inspired by the moodboard files.
2. RAW PHOTOGRAPHIC FIDELITY: Synthesize instructions that prioritize 600 DPI museum-grade optical definition, visible skin pores, natural skin texture, realistic teeth texture, natural tooth alignment, authentic gum line, subtle dental translucency, minor epidermal blemishes, and clean edge contrast. Strictly avoid plastic skin, over-smoothing, waxy softening, artificial airbrushing, or unnatural dentures/teeth.
3. MODULAR LEVERS: Extract 1 to 5 specific, high-value visual keyword descriptors directly inferred from the moodboard images for each of the 9 categories so the user can perform high-level macro adjustments in the Tag Studio. Never reuse placeholder example text.
4. COMPLETENESS: Never omit categories. Always provide relevant visual tags across all 9 dimensions.
```

#### Verbatim User Content Template (`user_baseline_template.txt`):
```text
USER CREATIVE BASELINE & INTENT:
<user_requirements>
{USER_PROMPT}
</user_requirements>

Analyze the moodboard images in conjunction with the user's creative requirements. Synthesize the optimal Master Generation Prompt with raw photo authenticity, visible skin pores, natural skin texture, realistic teeth texture, natural tooth alignment, authentic gum line, subtle dental translucency, minor skin blemishes, natural light, and authentic physical materials, breaking down its core visual levers across all 9 categories.

```

#### Fallback Category Defaults (`DEFAULT_FALLBACK_TAGS`):
If the vision model returns an empty list for any category, the pipeline injects deterministic high-fidelity defaults:
```python
DEFAULT_FALLBACK_TAGS = {
    "subject_details": [{"label": "striking expressive subject"}, {"label": "natural authentic pose"}],
    "objects_props": [{"label": "curated designer furniture"}],
    "wardrobe_hair": [{"label": "tailored contemporary wardrobe"}, {"label": "styled textured hair"}],
    "environment": [{"label": "architectural spatial setting"}, {"label": "refined ambient light"}],
    "layout_framing": [{"label": "cinematic rule-of-thirds composition"}],
    "lighting": [{"label": "directional soft natural key light"}],
    "color_profile": [{"label": "muted rich editorial palette"}],
    "camera_optics": [{"label": "85mm prime lens f/1.8"}],
    "mood_era": [{"label": "timeless candid vibe"}],
}
```

---

### 3.2. Step 1B: Re-sync Master Prompt from Visual Levers

When the user toggles, adds, or edits tags in the Tag Studio UI, `VisionService.resync_master_prompt` calls Gemini Vision to fluidly re-harmonize the Master Generation Prompt and narrative.

* **API Method**: `client.models.generate_content`
* **Target Model**: `gemini-3.5-flash-lite` (or user-selected model)
* **Configuration**: `types.GenerateContentConfig(system_instruction=RESYNC_MASTER_PROMPT_SYSTEM, response_mime_type="application/json", temperature=0.4)`
* **Source Files**: `src/app/prompts/resync_master_prompt_system.txt`, `src/app/prompts/resync_master_prompt_template.txt`

#### Verbatim System Prompt (`resync_master_prompt_system.txt`):
```text
You are an executive visual director, master cinematographer, and elite image generation prompt architect.
Your mission is to re-synthesize and harmonize the Master Generation Prompt and core scene narrative after the user has edited, added, or removed specific visual levers across the 9 creative categories.

You must return a single, valid JSON object with EXACTLY this structure:
{
  "master_prompt": "A complete, highly polished, evocative Master Generation Prompt designed to produce the definitive image matching the updated visual levers. Fluidly integrate all scene elements, subject details, wardrobe, environment, lighting, optics, color profile, and artistic aesthetic into a cohesive, cinematic description.",
  "narrative": "A concise 1-2 sentence core creative scene logline capturing the updated primary subject, action, setting, and emotional tone."
}

Directives:
1. HARMONIOUS SYNTHESIS: Weave all updated category tags into natural, evocative directorial prose. Avoid generating a mechanical comma-separated tag list or keyword prefixes (never use 'Subject:', 'Environment:', 'Composition:', or 'Lighting & Color:').
2. PRESERVE INTENT: Keep the original creative tone and spirit intact while seamlessly incorporating all newly added, edited, or modified tags.
3. RAW PHOTOGRAPHIC FIDELITY: Prioritize authentic analog cues ("raw photo", "visible skin pores", "natural skin texture", "realistic teeth texture", "natural tooth alignment", "authentic gum line", "subtle dental translucency", "minor skin blemishes", "natural light", "optical lens characteristics"). Specify concrete camera optics with exact numeric aperture stops (such as f/1.4, f/1.8, f/2.8, f/4, f/8) to control optical depth rather than vague generic terms like "shallow depth of field".
4. ZERO SYNTHETIC BUZZWORDS: Strictly NEVER use "photorealistic", "photorealism", "hyperrealistic", or "4K".
5. CONCISENESS & PRECISION: Keep the prompt dense, purposeful, and free of filler phrases.
```

#### Verbatim User Content Template (`resync_master_prompt_template.txt`):
```text
The user has updated the visual direction and tags for this scene. Re-harmonize and update the Master Generation Prompt and narrative accordingly.

<scene_narrative>
{CURRENT_NARRATIVE}
</scene_narrative>

<previous_master_prompt>
{PREVIOUS_MASTER_PROMPT}
</previous_master_prompt>

<updated_visual_levers>
{UPDATED_CATEGORIES_JSON}
</updated_visual_levers>

Synthesize the definitive updated Master Generation Prompt and core narrative reflecting all active tags above.
```

---

### 3.3. Step 1C: Concurrent 4-Candidate Baseline Generation

`GenerationService.generate_4_baselines` executes 4 parallel image generation tasks with 4 randomized seeds, compiling the master prompt together with negative prompt filtering and 600 DPI quality metadata.

#### Prompt Resolution Priority:
```python
if prompt_override and prompt_override.strip():
    compiled_prompt = prompt_override.strip()
elif master_prompt and str(master_prompt).strip():
    compiled_prompt = str(master_prompt).strip()
else:
    compiled_prompt = compile_prompt(narrative=narrative, categories=categories)
```

#### Modular Scene Compiler (`compile_prompt`):
Used if `master_prompt` is missing or when programmatically building the prompt from tags:
```python
def compile_prompt(narrative=None, categories=None, custom_tags=None, prompt_override=None) -> str:
    if prompt_override and prompt_override.strip():
        return prompt_override.strip()
    sections = []
    if narrative and narrative.strip():
        sections.append(narrative.strip())
    cats = categories or {}
    subject_labels = extract_category_labels(cats, "subject_details")
    wardrobe_labels = extract_category_labels(cats, "wardrobe_hair")
    object_labels = extract_category_labels(cats, "objects_props")
    env_labels = extract_category_labels(cats, "environment")
    framing_labels = extract_category_labels(cats, "layout_framing")
    camera_labels = extract_category_labels(cats, "camera_optics")
    lighting_labels = extract_category_labels(cats, "lighting")
    color_labels = extract_category_labels(cats, "color_profile")
    mood_labels = extract_category_labels(cats, "mood_era")
    all_custom = [c.strip() for c in (custom_tags or []) if c and c.strip()] + extract_category_labels(cats, "custom")

    if subject_labels or wardrobe_labels:
        parts = []
        if subject_labels: parts.append(", ".join(subject_labels))
        if wardrobe_labels: parts.append(f"wearing {', '.join(wardrobe_labels)}")
        sections.append(f"Subject: {', '.join(parts)}.")

    if env_labels or object_labels:
        parts = []
        if env_labels: parts.append(f"set in {', '.join(env_labels)}")
        if object_labels: parts.append(f"featuring {', '.join(object_labels)}")
        sections.append(f"Environment: {', '.join(parts)}.")

    if framing_labels or camera_labels:
        parts = []
        if framing_labels: parts.append(", ".join(framing_labels))
        if camera_labels: parts.append(f"shot on {', '.join(camera_labels)}")
        sections.append(f"Composition: {', '.join(parts)}.")

    if lighting_labels or color_labels:
        parts = []
        if lighting_labels: parts.append(f"illuminated with {', '.join(lighting_labels)}")
        if color_labels: parts.append(f"color palette of {', '.join(color_labels)}")
        sections.append(f"Lighting & Color: {', '.join(parts)}.")

    if mood_labels:
        sections.append(f"Aesthetic: {', '.join(mood_labels)}.")
    if all_custom:
        sections.append(f"Details: {', '.join(all_custom)}.")

    compiled = " ".join(sections).strip()
    return compiled or (narrative.strip() if narrative else "A high-fashion cinematic scene with exquisite detail.")
```

#### Quality Suffix & Negative Prompt Templates:
* **Suffix Template (`image_generation_suffix.txt`)**:
  ```text
  Resolution: {RESOLUTION} (Aspect ratio: {ASPECT_RATIO}). 600 DPI ultra-high-resolution print quality. Seed: {SEED}. Do not include: {NEGATIVE_PROMPT}.
  ```
* **Default Negative Prompt (`defaults.json`)**:
  ```json
  {
    "negative_prompt": "photorealistic render, 3d render, cgi, digital art, illustration, cartoon, anime, airbrushed, plastic skin, waxy skin, porcelain doll skin, artificial smoothing, beauty filter, doll face, fake reflections, studio flash glare, over-processed, oversaturated, perfect smooth skin, blurry, low resolution, pixelated, compression artifacts, distorted anatomy, loss of detail, muddy background, low quality scan"
  }
  ```

#### Wire Payload Dispatched to Google GenAI:
For Gemini Multimodal Image Models (`gemini-3-pro-image`, `gemini-3.1-flash-image`):
```python
res_tuple = ASPECT_RATIO_RESOLUTIONS.get(aspect_ratio, (3840, 2133))
suffix = IMAGE_GENERATION_SUFFIX.format(
    RESOLUTION=f"{res_tuple[0]}x{res_tuple[1]}",
    ASPECT_RATIO=aspect_ratio,
    SEED=seed,
    NEGATIVE_PROMPT=negative_prompt,
)
full_prompt = f"{positive_prompt.rstrip()} {suffix.strip()}"

response = await client.models.generate_content(
    model="gemini-3-pro-image",
    contents=[full_prompt],
)
```

#### Concrete Wire Example for Baseline Candidate #1:
```text
Raw photo of 2 pan Asian siblings in a modernist sunlit living room. An energetic 6-year-old boy with tousled dark hair jumps off a terracotta sofa holding a makeshift crimson silk cape mid-flight. His 14-year-old sister sits cross-legged on the sofa wearing an oversized cream knit sweater, laughing and clapping. Natural direct late-afternoon window sunlight casts soft directional shadows. Shot on 35mm prime lens with natural grain, visible skin pores, fine facial peach fuzz, and authentic texture. Resolution: 3840x2133 (Aspect ratio: 1.8:1). 600 DPI ultra-high-resolution print quality. Seed: 8492014. Do not include: photorealistic render, 3d render, cgi, digital art, illustration, cartoon, anime, airbrushed, plastic skin, waxy skin, porcelain doll skin, artificial smoothing, beauty filter, doll face, fake reflections, studio flash glare, over-processed, oversaturated, perfect smooth skin, blurry, low resolution, pixelated, compression artifacts, distorted anatomy, loss of detail, muddy background, low quality scan.
```

---

### 3.4. Step 1D: Direct User Photo Ingestion

When a user provides their own photograph via `/api/moodboard/upload-photo` (`GenerationService.register_uploaded_photo`):
1. **Aspect Ratio Auto-Detection**: Calculates `orig_w / orig_h` and matches against standard ratios (`1:1`, `16:9`, `9:16`, `21:9`, `2:3`, `3:2`, `4:5`, `5:4`, `3:4`, `4:3`, `1.8:1`, `1.85:1`).
2. **Metadata Registration**: Embeds 600 DPI metadata and saves the master PNG directly to storage.
3. **Pipeline Initialization**: Creates a baseline database record with `compiled_prompt = "Uploaded Reference Image"` and seed assignment, allowing the user to immediately transition into Step 2 Refinement or Wardrobe Studio without moodboard extraction.

---

## 4. Step 2: Iterative Refinement & Wardrobe Studio

### 4.1. Step 2A: Conversational Natural Language Refinement

`GenerationService.refine_generation` executes reference-conditioned edits conditioned on the parent baseline image bytes and free-text user directions.

* **API Method**: `client.models.generate_content`
* **Target Model**: `gemini-3-pro-image` (or user-selected image model)
* **Conditioning**: `[to_image_part(parent_image_bytes), full_prompt]`
* **Source Files**: `src/app/prompts/refinement_system.txt`, `src/app/prompts/image_generation_suffix.txt`

#### Verbatim Refinement System Prompt (`refinement_system.txt`):
```text
You are an image refinement assistant. You will receive a reference image and an edit instruction.

Use the reference image as a structural and visual anchor. Apply the user's requested modifications naturally, allowing interconnected visual elements — lighting, shadows, colors, materials, reflections — to adapt organically for realistic cohesion.

FIDELITY & TEXTURE LOCK:
- Maintain raw photo fidelity, 1:1 original sharpness, visible skin pores, natural skin texture, realistic teeth texture, natural tooth alignment, authentic gum line, subtle dental translucency, minor skin blemishes, natural light, and high-frequency fabric weaves.
- Strictly avoid plastic skin, waxy softening, artificial smoothing, airbrushing, or unnatural dentures/teeth.
- Maintain optical clarity without downsampling blur, compression artifacts, or pixelation.
- Ensure strict visual fidelity, natural texture, and sharpness on all unedited areas.


EDIT INSTRUCTION:
<edit>
{USER_PROMPT}
</edit>
```

#### Wire Payload Dispatched to Google GenAI:
```python
compiled_prompt = REFINEMENT_SYSTEM_PROMPT.replace("{USER_PROMPT}", user_prompt.strip())
suffix = IMAGE_GENERATION_SUFFIX.format(
    RESOLUTION=f"{res_w}x{res_h}",
    ASPECT_RATIO=aspect_ratio,
    SEED=seed,
    NEGATIVE_PROMPT=negative_prompt,
)
full_prompt = f"{compiled_prompt.rstrip()} {suffix.strip()}"

contents = [
    to_image_part(parent_image_bytes),
    full_prompt
]

response = await client.models.generate_content(
    model="gemini-3-pro-image",
    contents=contents,
)
```

#### Concrete Wire Example for Conversational Refinement:
```text
[IMAGE PART: 3840x2133 PNG parent image bytes]
[TEXT PART]:
You are an image refinement assistant. You will receive a reference image and an edit instruction.

Use the reference image as a structural and visual anchor. Apply the user's requested modifications naturally, allowing interconnected visual elements — lighting, shadows, colors, materials, reflections — to adapt organically for realistic cohesion.

FIDELITY & TEXTURE LOCK:
- Maintain raw photo fidelity, 1:1 original sharpness, visible skin pores, natural skin texture, realistic teeth texture, natural tooth alignment, authentic gum line, subtle dental translucency, minor skin blemishes, natural light, and high-frequency fabric weaves.
- Strictly avoid plastic skin, waxy softening, artificial smoothing, airbrushing, or unnatural dentures/teeth.
- Maintain optical clarity without downsampling blur, compression artifacts, or pixelation.
- Ensure strict visual fidelity, natural texture, and sharpness on all unedited areas.


EDIT INSTRUCTION:
<edit>
Change the boy's red cape to dark forest green corduroy fabric and add warm sunset golden hour lighting from the left window.
</edit> Resolution: 3840x2133 (Aspect ratio: 1.8:1). 600 DPI ultra-high-resolution print quality. Seed: 8492014. Do not include: photorealistic render, 3d render, cgi, digital art, illustration, cartoon, anime, airbrushed, plastic skin, waxy skin, porcelain doll skin, artificial smoothing, beauty filter, doll face, fake reflections, studio flash glare, over-processed, oversaturated, perfect smooth skin, unnaturally white teeth, glowing teeth, fused teeth, missing teeth, extra teeth, unnatural dentures, solid white bar teeth, blurry, low resolution, pixelated, compression artifacts, distorted anatomy, loss of detail, muddy background, low quality scan.
```

---

### 4.2. Step 2B: Seed-Locked Fine-Tuning with Tag Delta Compiler

When fine-tuning via tag adjustments in Tag Studio, `GenerationService.fine_tune_generation` compiles a delta prompt comparing modified visual levers against the baseline snapshot while enforcing locked category anchors.

#### Delta Prompt Compiler Logic (`compile_delta_prompt`):
```python
def compile_delta_prompt(
    narrative=None, categories=None, baseline_narrative=None,
    baseline_categories=None, locked_categories=None, custom_tags=None, prompt_override=None
) -> str:
    if prompt_override and prompt_override.strip():
        return prompt_override.strip()
    if not baseline_categories or not isinstance(baseline_categories, dict):
        return compile_prompt(narrative=narrative, categories=categories, custom_tags=custom_tags)

    cats = categories or {}
    diff = get_modified_categories(cats, baseline_categories, narrative, baseline_narrative)

    if not diff["has_changes"]:
        return (
            "Visual Continuity: Faithfully preserve the character identity, pose, framing, and environment "
            "from the input reference image while subtly refining overall render fidelity and atmospheric coherence."
        )

    sections = [
        "Visual Reference Foundation: Use the reference image as the structural, character, and stylistic anchor. "
        "Maintain raw photo fidelity, 1:1 original source sharpness, visible skin pores, natural skin texture, "
        "realistic teeth texture, natural tooth alignment, authentic gum line, subtle dental translucency, "
        "minor skin blemishes, natural light, and natural micro-contrast. "
        "Apply the requested modifications below seamlessly, allowing all naturally interconnected visual elements—"
        "including lighting falloff, cast shadows, color bounce, material reactions, and environmental reflections—"
        "to adjust organically for realistic visual cohesion without waxy smoothing, artificial plastic finish, or compression degradation."
    ]

    adjustments = []
    if diff["narrative"] and narrative and narrative.strip():
        adjustments.append(f"Scene Direction: {narrative.strip()}")
    if diff["categories"].get("subject_details"):
        lbls = extract_category_labels(cats, "subject_details")
        if lbls: adjustments.append(f"Subject Details: {', '.join(lbls)}")
    if diff["categories"].get("wardrobe_hair"):
        lbls = extract_category_labels(cats, "wardrobe_hair")
        if lbls: adjustments.append(f"Wardrobe & Hairstyle: wearing {', '.join(lbls)}")
    if diff["categories"].get("objects_props"):
        lbls = extract_category_labels(cats, "objects_props")
        if lbls: adjustments.append(f"Objects & Props: featuring {', '.join(lbls)}")
    if diff["categories"].get("environment"):
        lbls = extract_category_labels(cats, "environment")
        if lbls: adjustments.append(f"Environment: set in {', '.join(lbls)}")
    if diff["categories"].get("layout_framing"):
        lbls = extract_category_labels(cats, "layout_framing")
        if lbls: adjustments.append(f"Framing & Layout: {', '.join(lbls)}")
    if diff["categories"].get("lighting"):
        lbls = extract_category_labels(cats, "lighting")
        if lbls: adjustments.append(f"Lighting: illuminated with {', '.join(lbls)}")
    if diff["categories"].get("color_profile"):
        lbls = extract_category_labels(cats, "color_profile")
        if lbls: adjustments.append(f"Color Profile: palette of {', '.join(lbls)}")
    if diff["categories"].get("camera_optics"):
        lbls = extract_category_labels(cats, "camera_optics")
        if lbls: adjustments.append(f"Camera & Optics: shot on {', '.join(lbls)}")
    if diff["categories"].get("mood_era"):
        lbls = extract_category_labels(cats, "mood_era")
        if lbls: adjustments.append(f"Aesthetic & Mood: {', '.join(lbls)}")
    if diff["categories"].get("custom"):
        lbls = extract_category_labels(cats, "custom")
        if lbls: adjustments.append(f"Custom Details: {', '.join(lbls)}")

    if adjustments:
        sections.append(f"Requested Modifications: {'. '.join(adjustments)}.")

    all_known = ["subject_details", "wardrobe_hair", "objects_props", "environment",
                 "layout_framing", "camera_optics", "lighting", "color_profile", "mood_era"]
    locked_set = set(locked_categories or [])
    preserved = [CATEGORY_DISPLAY_NAMES.get(k, k) for k in all_known if k in locked_set]
    if preserved:
        sections.append(
            f"Consistent Anchors: Maintain the core design, identity, and styling of {', '.join(preserved)}, "
            f"while allowing them to interact realistically with the updated scene conditions."
        )

    return " ".join(sections).strip()
```

---

### 4.3. Step 2C: Wardrobe Lookbook Sheet Auto-Segmentation

When a lookbook sheet, flat-lay, or product grid is uploaded, `WardrobeService.segment_and_save_sheet` uses Gemini Vision to detect, classify, and extract 2D bounding boxes for every individual garment.

* **API Method**: `client.models.generate_content`
* **Target Model**: `gemini-3.5-flash-lite` (or user-selected model)
* **Configuration**: `types.GenerateContentConfig(temperature=0.0, response_mime_type="application/json", response_schema=WardrobeSegmentationResult)`
* **Source File**: `src/app/prompts/wardrobe_segmentation.txt`

#### Wire Payload Sent to API:
```python
contents = [
    to_image_part(sheet_image_bytes),
    WARDROBE_SEGMENTATION_PROMPT
]
```

#### Verbatim Segmentation Prompt (`wardrobe_segmentation.txt`):
```text
You are an expert fashion catalog vision assistant and garment segmentation specialist.
Analyze this lookbook, product sheet, outfit flat-lay, or model photography image.

Perform an exhaustive scan of the entire image to detect every distinct, wearable garment piece, footwear item, and accessory present.

Detection & Segmentation Guidelines:
1. Exhaustive Decomposition:
   - Break down full outfits and multi-item shots into their individual standalone components.
   - If a model is wearing multiple layered garments, segment each layer separately:
     * Outerwear: Coats, jackets, blazers, trench coats, vests, hoodies, cardigans.
     * Tops: T-shirts, shirts, blouses, crop tops, knit sweaters, tank tops.
     * Bottoms: Trousers, jeans, shorts, skirts, sweatpants, leggings.
     * Footwear: Sneakers, boots, heels, loafers, sandals.
     * Accessories: Hats, caps, beanies, sunglasses/eyewear, scarves, belts, bags/totes, jewelry.
   - Only classify an item as "full_outfit" if it is a single-piece garment (such as a one-piece dress, jumpsuit, or romper) that cannot be split into top and bottom.

2. Accurate Bounding Box Boundaries:
   - Provide a tight, precise bounding box enclosing each detected item.
   - Use integer coordinates on a 0 to 1000 normalized scale [ymin, xmin, ymax, xmax], where (0, 0) is top-left and (1000, 1000) is bottom-right.
   - Include the entire visible extent of the item without clipping edges.

3. Descriptive Labels:
   - Provide clear, descriptive titles indicating color, material, and garment type (e.g. "Camel Wool Overcoat", "White Cotton T-Shirt", "Indigo Raw Denim Jeans", "White Leather Low-Top Sneakers", "Black Leather Crossbody Bag").

Output format must be valid JSON adhering strictly to the schema with an "items" array.
```

---

### 4.4. Step 2D: Vision Subject Grounding Pre-Pass

Before executing a wardrobe swap, `WardrobeService.ground_wardrobe_pins` analyzes the base scene image and pin drop coordinates to determine the targeted subject, anatomical location, and current attire, while generating explicit non-target subject guardrails.

* **API Method**: `client.models.generate_content`
* **Target Model**: `gemini-3.5-flash-lite` (or user-selected model)
* **Source File**: `src/app/prompts/subject_grounding_system.txt`

#### Wire Payload Sent to API:
```python
pin_lines = [
    f"- Pin #{p['pin_number']}: coordinate x={round(p['x']*100)}%, y={round(p['y']*100)}% | Assigned Garment: \"{p['label']}\" ({p['cat']})"
    for p in pin_assignments
]
pin_text = "DROPPED GARMENT PINS TO ANALYZE:\n" + "\n".join(pin_lines)

contents = [
    to_image_part(parent_scene_bytes),
    pin_text,
    SUBJECT_GROUNDING_PROMPT
]
```

#### Verbatim Subject Grounding Prompt (`subject_grounding_system.txt`):
```text
You are an expert visual director and character analyst.
You will be provided with:
1. A primary base scene image containing one or more subjects (people, models, characters).
2. A list of numbered garment pins, each with a spatial coordinate (x, y as percentages from 0% to 100% of image width and height, where x=0% is left, y=0% is top), an item label, and a category.

Your task:
Analyze the image at each pin coordinate and perform precise spatial grounding and character disambiguation.

For each pin:
1. Identify the exact target subject at that coordinate (e.g., "young boy standing on the left side with dark curly hair", "female model in the center").
2. Identify the specific body/anatomical location of the pin (e.g., "head / hair area", "upper torso / chest", "legs / waist", "feet").
3. Describe the natural spatial anchor in the scene (e.g., "upper-left quadrant (x: 32%, y: 25%)").
4. Describe the subject's current attire/state at that body location to be replaced (e.g., "currently bare-headed with messy brown hair", "wearing a plain white t-shirt").

Also, identify all other subjects in the scene who are NOT targeted by any pin, and write a strict non-target preservation guardrail (e.g., "The young girl standing on the right with blonde hair wearing a floral dress MUST remain completely untouched. Do NOT add any hat, cap, or clothing changes to her.").

Return ONLY a valid JSON object matching this exact schema:
{
  "grounded_pins": [
    {
      "pin_number": 1,
      "target_subject": "Detailed description of the specific subject at this pin",
      "body_location": "Anatomical location on the subject",
      "spatial_anchor": "Natural scene-space quadrant and position description",
      "current_attire": "Current clothing / hair state to be replaced"
    }
  ],
  "unmodified_subjects_guardrail": "Explicit instruction detailing any other subjects who must strictly remain unchanged"
}
```

---

### 4.5. Step 2E: Multi-Garment Wardrobe Composition

`GenerationService.compose_wardrobe` combines the base scene reference image and multiple cropped garment images into a multi-image generation call to Gemini.

* **API Method**: `client.models.generate_content`
* **Target Model**: `gemini-3-pro-image` (or user-selected image model)
* **Source Files**: `src/app/prompts/wardrobe_composition_system.txt`, `src/app/prompts/image_generation_suffix.txt`

#### Verbatim Composition System Prompt (`wardrobe_composition_system.txt`):
```text
You are an advanced fashion composition and styling director. 
You will receive:
1. A reference base image showing a scene with one or more subjects.
2. One or more reference garment images, each associated with a numbered pin, target subject description, anatomical location, and replacement instruction.

Your task is to produce a single, authentic raw photo cohesive image where:
- Target Subject Fidelity: Each designated garment is seamlessly swapped onto the EXACT target subject specified at the grounded location, tailored naturally to their body geometry and pose.
- Multi-Subject Invariance: Any other subjects or characters in the scene NOT targeted by a pin MUST REMAIN ENTIRELY UNCHANGED (preserve their exact original facial features, hairstyle, clothing, and accessories).
- Texture & Material Transfer: Fabric texture, weave, weight, material details, patterns, and folds from each reference garment are accurately transferred.
- Environmental Harmonization: Lighting, cast shadows, specular highlights, reflections, and ambient color bounce are realistically harmonized with the base scene's lighting environment.
- Background & Composition: Surrounding environment, background props, camera angle, and unmentioned elements remain strictly identical.
- Fidelity & Sharpness Lock: Maintain 1:1 original source sharpness, raw photo fidelity, crisp focus, visible skin pores, natural skin texture, realistic teeth texture, natural tooth alignment, authentic gum line, subtle dental translucency, minor skin blemishes, natural light, and authentic micro-textures. Strictly prevent plastic skin, airbrushed textures, waxy smoothing, or unnatural dentures/teeth on subjects and scene elements.


COMPOSITION INSTRUCTIONS:
{COMPOSITION_INSTRUCTIONS}
```

#### Multi-Image Wire Payload Assembly (`contents`):
```python
contents = [
    to_image_part(parent_scene_bytes),
    "Primary Base Scene Image above (showing the current model/subject)."
]

# Append each reference garment image with label
for item in garment_items:
    contents.append(f"Reference Garment #{item['pin_number']} (Label: {item['label']}):")
    contents.append(to_image_part(item["garment_bytes"]))

# Compile dynamic composition directives block
instruction_lines = []
for item in garment_items:
    instruction_lines.append(
        f"- [Garment Pin #{item['pin_number']}] \"{item['label']}\" ({item['category']}):\n"
        f"  * Target Subject: {item['target_subject']} at {item['body_location']} [{item['spatial_anchor']}].\n"
        f"  * Replacement Action: Replace {item['current_attire']} with the garment in Reference Garment #{item['pin_number']}.\n"
        f"  * Tailoring & Fit: Harmonize naturally with this exact subject's body geometry, pose, and ambient scene lighting."
    )

if unmodified_guardrail:
    instruction_lines.append(f"\nMULTI-SUBJECT INVARIANCE GUARDRAIL:\n- {unmodified_guardrail}")

if custom_styling_directive:
    instruction_lines.append(f"\nADDITIONAL STYLING DIRECTIVE:\n- {custom_styling_directive}")

compiled_prompt = WARDROBE_COMPOSITION_SYSTEM_PROMPT.replace(
    "{COMPOSITION_INSTRUCTIONS}",
    "\n".join(instruction_lines)
)
contents.append(compiled_prompt)

# Append quality suffix
suffix = IMAGE_GENERATION_SUFFIX.format(
    RESOLUTION=f"{res_w}x{res_h}",
    ASPECT_RATIO=aspect_ratio,
    SEED=seed,
    NEGATIVE_PROMPT=negative_prompt,
)
contents.append(suffix.strip())
```

#### Concrete Multi-Image Wire Example:
```text
[PART 1 - IMAGE]: 3840x2133 PNG base scene image
[PART 2 - TEXT]: "Primary Base Scene Image above (showing the current model/subject)."
[PART 3 - TEXT]: "Reference Garment #1 (Label: Camel Wool Overcoat):"
[PART 4 - IMAGE]: Cropped PNG bytes of Camel Wool Overcoat
[PART 5 - TEXT]:
You are an advanced fashion composition and styling director. 
You will receive:
1. A reference base image showing a scene with one or more subjects.
2. One or more reference garment images, each associated with a numbered pin, target subject description, anatomical location, and replacement instruction.

Your task is to produce a single, authentic raw photo cohesive image where:
- Target Subject Fidelity: Each designated garment is seamlessly swapped onto the EXACT target subject specified at the grounded location, tailored naturally to their body geometry and pose.
- Multi-Subject Invariance: Any other subjects or characters in the scene NOT targeted by a pin MUST REMAIN ENTIRELY UNCHANGED (preserve their exact original facial features, hairstyle, clothing, and accessories).
- Texture & Material Transfer: Fabric texture, weave, weight, material details, patterns, and folds from each reference garment are accurately transferred.
- Environmental Harmonization: Lighting, cast shadows, specular highlights, reflections, and ambient color bounce are realistically harmonized with the base scene's lighting environment.
- Background & Composition: Surrounding environment, background props, camera angle, and unmentioned elements remain strictly identical.
- Fidelity & Sharpness Lock: Maintain 1:1 original source sharpness, raw photo fidelity, crisp focus, visible skin pores, natural skin texture, realistic teeth texture, natural tooth alignment, authentic gum line, subtle dental translucency, minor skin blemishes, natural light, and authentic micro-textures. Strictly prevent plastic skin, airbrushed textures, waxy smoothing, or unnatural dentures/teeth on subjects and scene elements.


COMPOSITION INSTRUCTIONS:
- [Garment Pin #1] "Camel Wool Overcoat" (outerwear):
  * Target Subject: Young boy jumping mid-air on the left side at upper torso and shoulders [upper-left quadrant (x: 28%, y: 35%)].
  * Replacement Action: Replace makeshift crimson cape with the garment in Reference Garment #1.
  * Tailoring & Fit: Harmonize naturally with this exact subject's body geometry, pose, and ambient scene lighting.

MULTI-SUBJECT INVARIANCE GUARDRAIL:
- The 14-year-old sister sitting cross-legged on the sofa on the right MUST remain completely untouched (preserve her facial features, hair, and cream knit sweater).
[PART 6 - TEXT]:
Resolution: 3840x2133 (Aspect ratio: 1.8:1). 600 DPI ultra-high-resolution print quality. Seed: 8492014. Do not include: photorealistic render, 3d render, cgi, digital art, illustration, cartoon, anime, airbrushed, plastic skin, waxy skin, porcelain doll skin, artificial smoothing, beauty filter, doll face, fake reflections, studio flash glare, over-processed, oversaturated, perfect smooth skin, unnaturally white teeth, glowing teeth, fused teeth, missing teeth, extra teeth, unnatural dentures, solid white bar teeth, blurry, low resolution, pixelated, compression artifacts, distorted anatomy, loss of detail, muddy background, low quality scan.
```

---

### 4.6. Step 2F: Clothing Region Detection for Auto-Masking

`WardrobeService.detect_clothing_regions` analyzes a generated image to locate bounding boxes of clothing pieces, providing bounding-box overlays for one-click auto-masking in the Canvas Studio.

* **API Method**: `client.models.generate_content`
* **Target Model**: `gemini-3.5-flash-lite` (or user-selected model)
* **Configuration**: `types.GenerateContentConfig(temperature=0.0, response_mime_type="application/json", response_schema=ClothingRegionDetectionResult)`
* **Source File**: `src/app/prompts/clothing_region_detection.txt`

#### Verbatim Detection Prompt (`clothing_region_detection.txt`):
```text
You are an expert image analysis assistant. Analyze this generated portrait or fashion scene.
Identify the subject(s) and distinct clothing regions (e.g., jacket/top, shirt, pants/trousers, shoes, dress, skirt, hat) visible on each person.
For each detected clothing region, provide:
1. label: Concise description (e.g., "Subject Upper Torso - Jacket", "Subject Lower Body - Trousers", "Subject Footwear - Sneakers").
2. category: One of "tops", "bottoms", "outerwear", "footwear", "accessories", "full_outfit".
3. bbox: Normalized bounding box [ymin, xmin, ymax, xmax] as floats between 0.0 and 1.0.

Return ONLY a valid JSON array of objects:
[
  {
    "label": "Subject Upper Torso - Jacket",
    "category": "outerwear",
    "bbox": [0.25, 0.30, 0.65, 0.70]
  }
]
Do not include any markdown or explanations outside the JSON array.
```

---

## 5. Step 3: Canvas Studio (Spatial Inpainting)

`GenerationService.inpaint_region` executes localized inpainting on user-painted or auto-masked regions. It supplies the source image and binary mask (`#FFFFFF` = edit, `#000000` = preserve) to Gemini, strictly enforcing pixel preservation outside the mask boundary.

* **API Method**: `client.models.generate_content`
* **Target Model**: `gemini-3-pro-image` (Configured via `settings.INPAINT_MODEL`)
* **Configuration**: `types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"], image_config=types.ImageConfig(aspect_ratio=...))`
* **Source Files**: `src/app/prompts/inpaint_system.txt`, `src/app/prompts/inpaint_suffix.txt`

#### Wire Payload Sent to API (`contents`):
```python
spatial_prompt = INPAINT_SYSTEM_PROMPT.replace("{USER_PROMPT}", prompt.strip())
if negative_prompt:
    suffix = INPAINT_SUFFIX.replace("{NEGATIVE_PROMPT}", negative_prompt)
    spatial_prompt = f"{spatial_prompt}\n\n{suffix}"

contents = [
    base_image_pil,   # PIL.Image instance of source image
    mask_image_pil,   # PIL.Image instance of black & white mask
    spatial_prompt    # Formatted spatial prompt string
]
```

#### Verbatim Inpaint System Prompt (`inpaint_system.txt`):
```text
You are a precision image editor. You will receive two images and an edit instruction.

Image 1 — SOURCE IMAGE: The original artwork to be edited. Treat every pixel outside the mask region as read-only. Reproduce them with pixel-perfect fidelity.

Image 2 — MASK IMAGE: A black-and-white map. WHITE pixels mark the region you must edit. BLACK pixels mark the region you must preserve exactly — do not alter any color, texture, shading, edge, or detail in the black region.

EDIT INSTRUCTION:
<edit>
{USER_PROMPT}
</edit>

Rules:
1. Apply the edit ONLY inside the white mask region.
2. Blend the edited region seamlessly with the surrounding untouched area (match lighting, shadow direction, color temperature, and texture scale at the mask boundary).
3. Preserve the exact composition, camera angle, depth of field, and aspect ratio ({ASPECT_RATIO}).
4. Output a single image matching the source resolution of {RESOLUTION} (Aspect ratio: {ASPECT_RATIO}).
5. Maintain raw photo fidelity, visible skin pores, natural skin texture, realistic teeth texture, natural tooth alignment, authentic gum line, subtle dental translucency, and minor skin blemishes. Strictly avoid plastic skin, waxy softening, artificial smoothing, airbrushing, or unnatural dentures/teeth.
6. Do not add, remove, or reposition any element outside the white mask region.
```

#### Verbatim Inpaint Suffix (`inpaint_suffix.txt`):
```text
Resolution: {RESOLUTION} (Aspect ratio: {ASPECT_RATIO}). Do not include: {NEGATIVE_PROMPT}. Do not change anything outside the white mask region.
```

#### Concrete Wire Example for Inpainting:
```text
[PART 1 - IMAGE]: PIL.Image (3840x2133 RGB)
[PART 2 - IMAGE]: PIL.Image (3840x2133 Grayscale / Black-and-White Binary Mask)
[PART 3 - TEXT]:
You are a precision image editor. You will receive two images and an edit instruction.

Image 1 — SOURCE IMAGE: The original artwork to be edited. Treat every pixel outside the mask region as read-only. Reproduce them with pixel-perfect fidelity.

Image 2 — MASK IMAGE: A black-and-white map. WHITE pixels mark the region you must edit. BLACK pixels mark the region you must preserve exactly — do not alter any color, texture, shading, edge, or detail in the black region.

EDIT INSTRUCTION:
<edit>
Replace the couch cushion with dark mustard yellow vintage velvet with tufted button detailing.
</edit>

Rules:
1. Apply the edit ONLY inside the white mask region.
2. Blend the edited region seamlessly with the surrounding untouched area (match lighting, shadow direction, color temperature, and texture scale at the mask boundary).
3. Preserve the exact composition, camera angle, depth of field, and aspect ratio (1.8:1).
4. Output a single image matching the source resolution of 3840x2133 (Aspect ratio: 1.8:1).
5. Maintain raw photo fidelity, visible skin pores, natural skin texture, realistic teeth texture, natural tooth alignment, authentic gum line, subtle dental translucency, and minor skin blemishes. Strictly avoid plastic skin, waxy softening, artificial smoothing, airbrushing, or unnatural dentures/teeth.
6. Do not add, remove, or reposition any element outside the white mask region.

Resolution: 3840x2133 (Aspect ratio: 1.8:1). Do not include: photorealistic render, 3d render, cgi, digital art, illustration, cartoon, anime, airbrushed, plastic skin, waxy skin, porcelain doll skin, artificial smoothing, beauty filter, doll face, fake reflections, studio flash glare, over-processed, oversaturated, perfect smooth skin, unnaturally white teeth, glowing teeth, fused teeth, missing teeth, extra teeth, unnatural dentures, solid white bar teeth, blurry, low resolution, pixelated, compression artifacts, distorted anatomy, loss of detail, muddy background, low quality scan. Do not change anything outside the white mask region.
```

---

## 6. Step 4: Export Studio & AI Master Restoration

`ExportService.prepare_export_master` executes a final master-grade raw photo restoration pass on the chosen generation. It locks the original seed, retains exact subject identity and geometry, and restores analog micro-textures, skin pores, and fabric weaves before saving as a 600 DPI 4K master.

* **API Method**: `client.models.generate_content`
* **Target Model**: `gemini-3-pro-image` (via `GenerationService._call_image_model`)
* **Conditioning**: `[to_image_part(source_image_bytes), full_prompt]`
* **Source Location**: `src/app/services/export_service.py` (`DEFAULT_UPSCALE_PROMPT`)

#### Verbatim Restoration Prompt (`DEFAULT_UPSCALE_PROMPT`):
```text
Restore, de-noise, and enhance the provided reference image as an authentic raw photo. Maximize optical resolution and crisp focus while strictly preserving original facial structures, visible skin pores, natural skin texture, realistic teeth texture, natural tooth alignment, authentic gum line, subtle dental translucency, minor skin blemishes, natural light, and overall composition. Focus on ensuring that all clothing, garments, fabric weaves, seams, and material textures are clear, tactile, and richly detailed.
```

#### Wire Payload Dispatched to Google GenAI:
```python
suffix = IMAGE_GENERATION_SUFFIX.format(
    RESOLUTION=f"{target_w}x{target_h}",
    ASPECT_RATIO=aspect_ratio,
    SEED=seed,
    NEGATIVE_PROMPT=negative_prompt,
)
full_prompt = f"{DEFAULT_UPSCALE_PROMPT.rstrip()} {suffix.strip()}"

contents = [
    to_image_part(source_image_bytes),
    full_prompt
]

response = await client.models.generate_content(
    model="gemini-3-pro-image",
    contents=contents,
)
```

---

## 7. Frontend UI Guidance, Placeholders & User Inputs

The frontend client provides specific prompt guidance, placeholders, and tooltips at each stage of the user journey:

### 7.1. Moodboard Ingestion (`src/frontend/src/components/MoodboardUploader.jsx`)
* **Prompt Label**: `Starting Scene Prompt *`
* **Textarea Placeholder**:
  ```text
  Enter the required starting scene direction, characters, mood, setting, lighting, and style overrides (e.g. 'A high-fashion editorial portrait in a sunlit modernist villa with tailored neutral wardrobe and warm film tones')...
  ```
* **Prompt Guidance**:
  ```text
  The AI Vision Director will synthesize your moodboard references together with this prompt to craft the optimal Master Prompt, 9-category visual levers, and 4 baseline candidates.
  ```

### 7.2. Refinement Chat (`src/frontend/src/components/RefinementChat.jsx`)
* **Sub-header Instruction**:
  ```text
  Direct changes naturally in plain English or use the Wardrobe Studio to swap outfits with reference images.
  ```
* **Empty State Suggested Prompts**:
  ```text
  Type instructions below like "Change the jacket to brown leather" or "Add warm late-afternoon sunlight".
  ```
* **Input Placeholder**:
  ```text
  Describe your refinements (e.g. 'Warm sunset golden hour lighting, softer depth of field')...
  ```

### 7.3. Canvas Studio Inpainting (`src/frontend/src/components/CanvasStudio.jsx`)
* **Prompt Input Placeholder**:
  ```text
  Describe only the change inside the painted region (e.g., 'replace with gold embroidery pattern and metallic sheen')...
  ```
* **Prompting Tips**:
  - Focus strictly on the selected area (e.g., *"change the leather jacket to dark forest green suede"*).
  - Specify color, texture, material, and finish for crisp adjustments.
  - One specific change per iteration yields the cleanest preservation of the background.

---

## 8. Telemetry & Observability Auditing Guide

Every API invocation and compiled prompt string is logged to disk in JSONL format for auditing:

1. **`storage/logs/vision_audit.jsonl`**:
   - `vision_request`: Logs the full system instruction (`extraction_system.txt`), user requirements, and reference moodboard image hashes.
   - `vision_response`: Logs the raw JSON response, extracted `master_prompt`, `narrative`, and category tag counts.
   - `resync_prompt_request` & `resync_prompt_response`: Logs re-sync calls and prompt evolution.
2. **`storage/logs/generation_audit.jsonl`**:
   - `baseline_single_request` / `baseline_batch_request`: Logs the exact compiled prompt, aspect ratio, seed, and negative tokens.
   - `refinement_request`: Logs the user prompt, wrapped system prompt (`refinement_system.txt`), seed, and parent image hash.
   - `inpaint_request`: Logs the spatial prompt, mask metrics (pixel coverage %, bounding box, centroid coordinates), and seed.
   - `export_prepare_started` / `export_prepare_completed`: Logs the AI master restoration prompt, resolution dimensions, and source generation ID.
3. **`storage/logs/wardrobe_audit.jsonl`**:
   - `wardrobe_segmentation_request`: Logs segmentation prompt, source sheet hash, and bounding boxes.
   - `wardrobe_grounding_request`: Logs dropped pin coordinates and subject grounding prompt.
   - `wardrobe_compose_request`: Logs multi-image composition prompt, grounded subjects, and guardrails.
