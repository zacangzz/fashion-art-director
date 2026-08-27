# Comprehensive Prompt & Template Registry

This document provides a comprehensive, verbatim catalog of every prompt, system directive, suffix template, and dynamic prompt compiler utilized across the entire lifecycle of the application.

---

## 1. Lifecycle Overview & Master Prompt Matrix

The application operates across a **4-Step Sequential Studio Architecture** with auxiliary specialized modules (Wardrobe Studio, Auto-Mask Detection, and AI Master Upscaling):

```
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│ Step 1: Art Direction & Moodboard Synthesis                                                │
│ ├─ Extraction System Prompt (extraction_system.txt)                                         │
│ ├─ User Baseline Template (user_baseline_template.txt)                                      │
│ ├─ Modular Scene Prompt Compiler (compile_prompt)                                           │
│ └─ Generation Suffix & Negative Prompt (image_generation_suffix.txt, defaults.json)         │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
                                              │
                                              ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│ Step 2: Iterative Refinement & Wardrobe Studio                                              │
│ ├─ Conversational Refinement Prompt (refinement_system.txt)                                 │
│ ├─ Delta Fine-Tuning Compiler (compile_delta_prompt)                                        │
│ ├─ Wardrobe Sheet Segmentation (wardrobe_segmentation.txt)                                  │
│ ├─ Vision Subject Grounding (subject_grounding_system.txt)                                  │
│ ├─ Clothing Region Detection (clothing_region_detection.txt)                                │
│ └─ Multi-Garment Composition (wardrobe_composition_system.txt)                              │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
                                              │
                                              ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│ Step 3: Canvas Studio (Spatial Inpainting)                                                  │
│ ├─ Spatial Masked Inpaint System (inpaint_system.txt)                                       │
│ └─ Inpaint Boundary & Negative Suffix (inpaint_suffix.txt)                                  │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
                                              │
                                              ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│ Step 4: Export Studio & AI Master Restoration                                               │
│ └─ AI Master Raw Photo Restoration Prompt (DEFAULT_UPSCALE_PROMPT)                          │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Master Prompt Inventory Table

| # | Prompt / Template Name | Source File / Location | Target AI Model | Lifecycle Stage | Primary Function |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **1** | **Extraction System Prompt** | `src/app/prompts/extraction_system.txt` | `gemini-3.1-flash-lite` | Step 1: Ingestion | Analyzes moodboard images and user intent to extract 9-category visual levers and master prompt JSON. |
| **2** | **User Baseline Template** | `src/app/prompts/user_baseline_template.txt` | `gemini-3.1-flash-lite` | Step 1: Ingestion | Wraps user creative prompt requirements into the vision model input payload. |
| **3** | **Default Negative Prompt** | `src/app/prompts/defaults.json` | `gemini-3.1-flash-lite-image` / `imagen` | Global / Generation | Baseline negative token filter eliminating synthetic/plastic/CGI artifacts and waxy smoothing. |
| **4** | **Image Generation Suffix** | `src/app/prompts/image_generation_suffix.txt` | `gemini-3.1-flash-lite-image` | Global / Generation | Injects aspect ratio, seed, negative prompt, and 600 DPI print quality metadata. |
| **5** | **Modular Prompt Compiler** | `src/app/services/generation_service.py` & `src/frontend/src/utils/promptCompiler.js` | `gemini-3.1-flash-lite-image` | Step 1: Baseline Generation | Programmatically constructs structured prompt paragraphs from 9-category visual tags. |
| **6** | **Refinement System Prompt** | `src/app/prompts/refinement_system.txt` | `gemini-3.1-flash-lite-image` | Step 2: Refinement | Governs reference-conditioned image-to-image natural language conversation edits. |
| **7** | **Delta Prompt Compiler** | `src/app/services/generation_service.py` & `src/frontend/src/utils/promptCompiler.js` | `gemini-3.1-flash-lite-image` | Step 2: Fine-Tuning | Compiles targeted modification directives while enforcing locked category anchors. |
| **8** | **Wardrobe Sheet Segmentation** | `src/app/prompts/wardrobe_segmentation.txt` | `gemini-3.1-flash-lite` | Step 2: Wardrobe Studio | Detects individual garments, categories, and bounding boxes from uploaded lookbook sheets. |
| **9** | **Subject Grounding System Prompt** | `src/app/prompts/subject_grounding_system.txt` | `gemini-3.1-flash-lite` | Step 2: Wardrobe Studio | Disambiguates scene characters at user pin coordinates and establishes non-target subject guardrails. |
| **10** | **Wardrobe Composition System Prompt** | `src/app/prompts/wardrobe_composition_system.txt` | `gemini-3.1-flash-lite-image` | Step 2: Wardrobe Studio | Orchestrates multi-reference garment swapping onto targeted subjects while maintaining background invariance. |
| **11** | **Clothing Region Detection Prompt** | `src/app/prompts/clothing_region_detection.txt` | `gemini-3.1-flash-lite` | Step 2 / 3: Auto-Masking | Scans generated scene to detect clothing bounding boxes for auto-masking overlays. |
| **12** | **Inpaint System Prompt** | `src/app/prompts/inpaint_system.txt` | `gemini-3.1-flash-image` | Step 3: Canvas Inpaint | Enforces strict pixel immutability outside mask boundaries and seamless edge blending. |
| **13** | **Inpaint Suffix** | `src/app/prompts/inpaint_suffix.txt` | `gemini-3.1-flash-image` | Step 3: Canvas Inpaint | Negative prompt and boundary constraint appendix for spatial inpainting. |
| **14** | **Default AI Upscale & Restoration Prompt** | `src/app/services/export_service.py` | `gemini-3.1-flash-lite-image` | Step 4: Export Master | Restores raw photo fidelity, film grain, fabric weave, visible skin pores, and natural textures. |

---

## 2. Step 1: Art Direction & Moodboard Synthesis

### 2.1. Extraction System Prompt
* **File Location**: `src/app/prompts/extraction_system.txt`
* **Target Model**: `gemini-3.1-flash-lite` (via `VisionService.extract_tag_studio_state`)
* **Output Format**: Structured JSON (`response_mime_type: "application/json"`)
* **Full Verbatim Content**:

```text
You are an executive visual director, master cinematographer, and elite image generation prompt architect.
Your mission is to analyze the reference moodboard images and user creative requirements, then synthesize the OPTIMAL, highest-fidelity generation prompt alongside its constituent visual levers.

You must return a single, valid JSON object with EXACTLY this structure:
{
  "master_prompt": "A complete, highly polished, evocative Master Generation Prompt designed to produce the definitive image matching the moodboard and requirements. Synthesize the scene, subject, wardrobe, environment, lighting, optics, color profile, and artistic aesthetic into a cohesive, cinematic description.",
  "narrative": "A concise 1-2 sentence core creative scene logline capturing the primary subject, action, setting, and emotional tone.",
  "categories": {
    "subject_details": [
      {"label": "e.g. young boy with copper ginger hair", "weight": 1.0},
      {"label": "e.g. seated with right hand raised to mouth", "weight": 1.0}
    ],
    "objects_props": [
      {"label": "e.g. terracotta mid-century outdoor sofa", "weight": 1.0},
      {"label": "e.g. woven slate blue cushions", "weight": 1.0}
    ],
    "wardrobe_hair": [
      {"label": "e.g. wind-tousled wavy ginger hair", "weight": 1.0},
      {"label": "e.g. cream ribbed cotton knit sweater", "weight": 1.0}
    ],
    "environment": [
      {"label": "e.g. sunlit modernist terrace patio", "weight": 1.0},
      {"label": "e.g. lush Mediterranean pine trees in background", "weight": 1.0}
    ],
    "layout_framing": [
      {"label": "e.g. medium-wide cinematic composition", "weight": 1.0},
      {"label": "e.g. rule-of-thirds asymmetric balance", "weight": 1.0}
    ],
    "lighting": [
      {"label": "e.g. warm direct late-afternoon golden sunlight", "weight": 1.0},
      {"label": "e.g. soft diffused ambient fill with gentle shadows", "weight": 1.0}
    ],
    "color_profile": [
      {"label": "e.g. warm terracotta, slate blue, and olive green palette", "weight": 1.0},
      {"label": "e.g. natural Kodak Portra film color grade", "weight": 1.0}
    ],
    "camera_optics": [
      {"label": "e.g. raw photo shot on 35mm analog film with fine film grain", "weight": 1.0},
      {"label": "e.g. 85mm f/1.4 prime lens with natural light and slight motion blur", "weight": 1.0},
      {"label": "e.g. visible skin pores, natural skin texture, stray hairs, and minor skin blemishes", "weight": 1.0}
    ],
    "mood_era": [
      {"label": "e.g. 1970s retro luxury editorial vibe with subtle dust and scratches", "weight": 1.0},
      {"label": "e.g. playful, candid high-end commercial aesthetic", "weight": 1.0}
    ]
  }
}

Directives:
1. MASTER PROMPT EXCELLENCE: The `master_prompt` must be rich, concrete, evocative, and free of vague synthetic buzzwords. Strictly NEVER use "photorealistic", "photorealism", "hyperrealistic", or "4K". Instead, prioritize authentic analog cues ("raw photo", "film grain", "subtle dust and scratches", "visible skin pores", "natural skin texture", "stray hairs", "minor skin blemishes", "slight motion blur", "natural light"), specific camera optics (e.g. 35mm/medium format prime lenses), realistic lighting behavior, physical materials, and atmospheric depth inspired by the moodboard files.
2. RAW PHOTOGRAPHIC FIDELITY: Synthesize instructions that prioritize 600 DPI museum-grade optical definition, visible skin pores, natural skin texture, fine stray hairs, minor epidermal blemishes, subtle film grain, and clean edge contrast. Strictly avoid plastic skin, over-smoothing, waxy softening, or artificial airbrushing.
3. MODULAR LEVERS: Extract 2 to 5 specific, high-value visual keyword descriptors for each of the 9 categories so the user can perform high-level macro adjustments in the Tag Studio.
4. COMPLETENESS: Never omit categories. Always provide relevant visual tags across all 9 dimensions.
```

---

### 2.2. User Baseline Template
* **File Location**: `src/app/prompts/user_baseline_template.txt`
* **Target Model**: `gemini-3.1-flash-lite`
* **Placeholders**: `{USER_PROMPT}`
* **Full Verbatim Content**:

```text
USER CREATIVE BASELINE & INTENT:
<user_requirements>
{USER_PROMPT}
</user_requirements>

Analyze the moodboard images in conjunction with the user's creative requirements. Synthesize the optimal Master Generation Prompt with raw photo authenticity, fine film grain, visible skin pores, natural skin texture, stray hairs, minor skin blemishes, natural light, and authentic physical materials, breaking down its core visual levers across all 9 categories.
```

---

### 2.3. Default Negative Prompt
* **File Location**: `src/app/prompts/defaults.json`
* **Target Models**: `gemini-3.1-flash-lite-image`, `imagen-3.0-capability-001`
* **Full Verbatim Content**:

```json
{
  "negative_prompt": "photorealistic render, 3d render, cgi, digital art, illustration, cartoon, anime, airbrushed, plastic skin, waxy skin, porcelain doll skin, artificial smoothing, beauty filter, doll face, fake reflections, studio flash glare, over-processed, oversaturated, perfect smooth skin, blurry, low resolution, pixelated, compression artifacts, distorted anatomy, loss of detail, muddy background, low quality scan"
}
```

---

### 2.4. Image Generation Suffix
* **File Location**: `src/app/prompts/image_generation_suffix.txt`
* **Target Model**: `gemini-3.1-flash-lite-image`
* **Placeholders**: `{ASPECT_RATIO}`, `{SEED}`, `{NEGATIVE_PROMPT}`
* **Full Verbatim Content**:

```text
Aspect ratio: {ASPECT_RATIO}. 600 DPI ultra-high-resolution print quality. Seed: {SEED}. Do not include: {NEGATIVE_PROMPT}.
```

---

### 2.5. Modular Scene Prompt Compiler
* **Source Location**: `src/app/services/generation_service.py` (`compile_prompt`) & `src/frontend/src/utils/promptCompiler.js` (`compileModularPrompt`)
* **Logic**: Iterates over enabled TagChips in the 9 visual categories and synthesizes a structured natural-language prompt paragraph.

```python
def compile_prompt(
    narrative: Optional[str] = None,
    categories: Optional[Dict[str, Any]] = None,
    custom_tags: Optional[List[str]] = None,
    prompt_override: Optional[str] = None,
) -> str:
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
    custom_labels = [c.strip() for c in (custom_tags or []) if c and c.strip()]
    custom_cat_labels = extract_category_labels(cats, "custom")
    all_custom = custom_labels + custom_cat_labels

    if subject_labels or wardrobe_labels:
        parts = []
        if subject_labels:
            parts.append(", ".join(subject_labels))
        if wardrobe_labels:
            parts.append(f"wearing {', '.join(wardrobe_labels)}")
        sections.append(f"Subject: {', '.join(parts)}.")

    if env_labels or object_labels:
        parts = []
        if env_labels:
            parts.append(f"set in {', '.join(env_labels)}")
        if object_labels:
            parts.append(f"featuring {', '.join(object_labels)}")
        sections.append(f"Environment: {', '.join(parts)}.")

    if framing_labels or camera_labels:
        parts = []
        if framing_labels:
            parts.append(", ".join(framing_labels))
        if camera_labels:
            parts.append(f"shot on {', '.join(camera_labels)}")
        sections.append(f"Composition: {', '.join(parts)}.")

    if lighting_labels or color_labels:
        parts = []
        if lighting_labels:
            parts.append(f"illuminated with {', '.join(lighting_labels)}")
        if color_labels:
            parts.append(f"color palette of {', '.join(color_labels)}")
        sections.append(f"Lighting & Color: {', '.join(parts)}.")

    if mood_labels:
        sections.append(f"Aesthetic: {', '.join(mood_labels)}.")

    if all_custom:
        sections.append(f"Details: {', '.join(all_custom)}.")

    compiled = " ".join(sections).strip()
    return compiled or (narrative.strip() if narrative else "A high-fashion cinematic scene with exquisite detail.")
```

---

### 2.6. Default Fallback Category Tags
* **Source Location**: `src/app/services/vision_service.py` (`DEFAULT_FALLBACK_TAGS`)
* **Purpose**: Used when vision model extraction produces empty arrays for any category.

```python
DEFAULT_FALLBACK_TAGS = {
    "subject_details": [
        {"label": "striking expressive subject", "weight": 1.0},
        {"label": "natural authentic pose", "weight": 1.0},
    ],
    "objects_props": [
        {"label": "curated designer furniture", "weight": 1.0},
    ],
    "wardrobe_hair": [
        {"label": "tailored contemporary wardrobe", "weight": 1.0},
        {"label": "styled textured hair", "weight": 1.0},
    ],
    "environment": [
        {"label": "architectural spatial setting", "weight": 1.0},
        {"label": "refined ambient light", "weight": 1.0},
    ],
    "layout_framing": [
        {"label": "cinematic rule-of-thirds composition", "weight": 1.0},
    ],
    "lighting": [
        {"label": "directional soft natural key light", "weight": 1.0},
    ],
    "color_profile": [
        {"label": "muted rich editorial palette", "weight": 1.0},
    ],
    "camera_optics": [
        {"label": "85mm prime lens f/1.8 shallow depth", "weight": 1.0},
    ],
    "mood_era": [
        {"label": "timeless candid vibe", "weight": 1.0},
    ],
}
```

---

## 3. Step 2: Iterative Refinement & Wardrobe Studio

### 3.1. Refinement System Prompt
* **File Location**: `src/app/prompts/refinement_system.txt`
* **Target Model**: `gemini-3.1-flash-lite-image` (via `/api/refine` & `GenerationService.refine_generation`)
* **Conditioning**: Input reference image bytes + user natural language instruction.
* **Placeholders**: `{USER_PROMPT}`
* **Full Verbatim Content**:

```text
You are an image refinement assistant. You will receive a reference image and an edit instruction.

Use the reference image as a structural and visual anchor. Apply the user's requested modifications naturally, allowing interconnected visual elements — lighting, shadows, colors, materials, reflections — to adapt organically for realistic cohesion.

FIDELITY & TEXTURE LOCK:
- Maintain raw photo fidelity, 1:1 original sharpness, visible skin pores, natural skin texture, stray hairs, minor skin blemishes, subtle film grain, natural light, and high-frequency fabric weaves.
- Strictly avoid plastic skin, waxy softening, artificial smoothing, or airbrushing.
- Maintain optical clarity without downsampling blur, compression artifacts, or pixelation.
- Ensure strict visual fidelity, natural texture, and sharpness on all unedited areas.


EDIT INSTRUCTION:
<edit>
{USER_PROMPT}
</edit>
```

---

### 3.2. Delta Fine-Tuning Compiler
* **Source Location**: `src/app/services/generation_service.py` (`compile_delta_prompt`) & `src/frontend/src/utils/promptCompiler.js` (`compileDeltaPrompt`)
* **Purpose**: Compiles a prompt focused strictly on differences between the current modified tags and baseline snapshot, while anchoring locked categories.

```python
def compile_delta_prompt(
    narrative: Optional[str] = None,
    categories: Optional[Dict[str, Any]] = None,
    baseline_narrative: Optional[str] = None,
    baseline_categories: Optional[Dict[str, Any]] = None,
    locked_categories: Optional[List[str]] = None,
    custom_tags: Optional[List[str]] = None,
    prompt_override: Optional[str] = None,
) -> str:
    if prompt_override and prompt_override.strip():
        return prompt_override.strip()

    if not baseline_categories or not isinstance(baseline_categories, dict):
        return compile_prompt(
            narrative=narrative,
            categories=categories,
            custom_tags=custom_tags,
            prompt_override=prompt_override,
        )

    cats = categories or {}
    diff = get_modified_categories(
        current_categories=cats,
        baseline_categories=baseline_categories,
        current_narrative=narrative,
        baseline_narrative=baseline_narrative,
    )

    if not diff["has_changes"]:
        return (
            "Visual Continuity: Faithfully preserve the character identity, pose, framing, and environment "
            "from the input reference image while subtly refining overall render fidelity and atmospheric coherence."
        )

    sections = [
        "Visual Reference Foundation: Use the reference image as the structural, character, and stylistic anchor. "
        "Maintain 1:1 original source sharpness and high-fidelity texture rendering (skin pores, crisp focus, natural micro-contrast). "
        "Apply the requested modifications below seamlessly, allowing all naturally interconnected visual elements—including lighting falloff, cast shadows, color bounce, material reactions, and environmental reflections—to adjust organically for realistic visual cohesion without waxy smoothing or compression degradation."
    ]

    adjustments = []
    if diff["narrative"] and narrative and narrative.strip():
        adjustments.append(f"Scene Direction: {narrative.strip()}")

    if diff["categories"].get("subject_details"):
        lbls = extract_category_labels(cats, "subject_details")
        if lbls:
            adjustments.append(f"Subject Details: {', '.join(lbls)}")

    if diff["categories"].get("wardrobe_hair"):
        lbls = extract_category_labels(cats, "wardrobe_hair")
        if lbls:
            adjustments.append(f"Wardrobe & Hairstyle: wearing {', '.join(lbls)}")

    if diff["categories"].get("objects_props"):
        lbls = extract_category_labels(cats, "objects_props")
        if lbls:
            adjustments.append(f"Objects & Props: featuring {', '.join(lbls)}")

    if diff["categories"].get("environment"):
        lbls = extract_category_labels(cats, "environment")
        if lbls:
            adjustments.append(f"Environment: set in {', '.join(lbls)}")

    if diff["categories"].get("layout_framing"):
        lbls = extract_category_labels(cats, "layout_framing")
        if lbls:
            adjustments.append(f"Framing & Layout: {', '.join(lbls)}")

    if diff["categories"].get("lighting"):
        lbls = extract_category_labels(cats, "lighting")
        if lbls:
            adjustments.append(f"Lighting: illuminated with {', '.join(lbls)}")

    if diff["categories"].get("color_profile"):
        lbls = extract_category_labels(cats, "color_profile")
        if lbls:
            adjustments.append(f"Color Profile: palette of {', '.join(lbls)}")

    if diff["categories"].get("camera_optics"):
        lbls = extract_category_labels(cats, "camera_optics")
        if lbls:
            adjustments.append(f"Camera & Optics: shot on {', '.join(lbls)}")

    if diff["categories"].get("mood_era"):
        lbls = extract_category_labels(cats, "mood_era")
        if lbls:
            adjustments.append(f"Aesthetic & Mood: {', '.join(lbls)}")

    if diff["categories"].get("custom"):
        lbls = extract_category_labels(cats, "custom")
        if lbls:
            adjustments.append(f"Custom Details: {', '.join(lbls)}")

    if adjustments:
        sections.append(f"Requested Modifications: {'. '.join(adjustments)}.")

    all_known_categories = [
        "subject_details",
        "wardrobe_hair",
        "objects_props",
        "environment",
        "layout_framing",
        "camera_optics",
        "lighting",
        "color_profile",
        "mood_era",
    ]
    locked_set = set(locked_categories or [])
    preserved_categories = [
        CATEGORY_DISPLAY_NAMES.get(k, k)
        for k in all_known_categories
        if k in locked_set
    ]

    if preserved_categories:
        sections.append(
            f"Consistent Anchors: Maintain the core design, identity, and styling of {', '.join(preserved_categories)}, while allowing them to interact realistically with the updated scene conditions."
        )

    return " ".join(sections).strip()
```

---

### 3.3. Wardrobe Sheet Segmentation Prompt
* **File Location**: `src/app/prompts/wardrobe_segmentation.txt`
* **Target Model**: `gemini-3.1-flash-lite` (via `WardrobeService.segment_and_save_sheet`)
* **Generation Config**: `temperature=0.0`, `response_mime_type="application/json"`, `response_schema=WardrobeSegmentationResult`
* **Output Format**: Structured JSON object with an `items` array containing `DetectedGarment` objects (`label`, `category`, and integer `box_2d` in `[ymin, xmin, ymax, xmax]` 0..1000 scale).
* **Full Verbatim Content**:

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

### 3.4. Subject Grounding System Prompt (Pre-Pass)
* **File Location**: `src/app/prompts/subject_grounding_system.txt`
* **Target Model**: `gemini-3.1-flash-lite` (via `WardrobeService.ground_wardrobe_pins`)
* **Output Format**: JSON object with grounded pins and non-target preservation guardrails.
* **Full Verbatim Content**:

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

#### Pin Summary Text Block Formatter:
Constructed dynamically in `ground_wardrobe_pins` before sending to the model:
```python
# Format each dropped pin:
f"- Pin #{pin_num}: coordinate x={round(x*100)}%, y={round(y*100)}% | Assigned Garment: \"{label}\" ({cat})"
```

#### Deterministic Fallback Spatial Grounding Heuristic:
If vision model grounding fails or is offline:
```python
"Strictly preserve all other subjects and non-targeted character features, clothing, and hairstyles in the scene exactly as shown in the reference image without any alterations."
```

---

### 3.5. Wardrobe Composition System Prompt
* **File Location**: `src/app/prompts/wardrobe_composition_system.txt`
* **Target Model**: `gemini-3.1-flash-lite-image` (via `/api/wardrobe/compose` & `GenerationService.compose_wardrobe`)
* **Placeholders**: `{COMPOSITION_INSTRUCTIONS}`
* **Input Parts**: Multi-image array containing:
  1. Base Image (`to_image_part(parent_bytes)`) + Text `"Primary Base Scene Image above (showing the current model/subject)."`
  2. For each garment pin: Text `"Reference Garment #{pin_num} (Label: {label}):"` + Image (`to_image_part(garment_bytes)`)
  3. Compiled System Directive with composition instructions.
* **Full Verbatim Content**:

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
- Fidelity & Sharpness Lock: Maintain 1:1 original source sharpness, raw photo fidelity, crisp focus, visible skin pores, natural skin texture, stray hairs, minor skin blemishes, fine film grain, natural light, and authentic micro-textures. Strictly prevent plastic skin, airbrushed textures, or waxy smoothing on subjects and scene elements.


COMPOSITION INSTRUCTIONS:
{COMPOSITION_INSTRUCTIONS}
```

#### Dynamic `{COMPOSITION_INSTRUCTIONS}` Builder:
Formatted in `compose_wardrobe`:
```text
- [Garment Pin #{pin_num}] "{item_label}" ({category}):
  * Target Subject: {target_subject} at {body_location} [{spatial_anchor}].
  * Replacement Action: Replace {current_attire} with the garment in Reference Garment #{pin_num}.
  * Tailoring & Fit: Harmonize naturally with this exact subject's body geometry, pose, and ambient scene lighting.

MULTI-SUBJECT INVARIANCE GUARDRAIL:
- {unmodified_subjects_guardrail}

ADDITIONAL STYLING DIRECTIVE:
- {custom_instruction}
```

---

### 3.6. Clothing Region Detection Prompt
* **File Location**: `src/app/prompts/clothing_region_detection.txt`
* **Target Model**: `gemini-3.1-flash-lite` (via `WardrobeService.detect_clothing_regions`)
* **Output Format**: JSON array of normalized bounding boxes `[ymin, xmin, ymax, xmax]` in float `0.0..1.0`.
* **Full Verbatim Content**:

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

## 4. Step 3: Canvas Studio (Spatial Inpainting)

### 4.1. Inpaint System Prompt
* **File Location**: `src/app/prompts/inpaint_system.txt`
* **Target Model**: `gemini-3.1-flash-image` (via `/api/inpaint` & `GenerationService.inpaint_region`)
* **Conditioning**: Base Image + Binary Mask Image (`#FFFFFF` = edit, `#000000` = preserve) + Prompt.
* **Placeholders**: `{USER_PROMPT}`
* **Full Verbatim Content**:

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
3. Preserve the exact composition, camera angle, depth of field, and aspect ratio.
4. Output a single image at the same resolution as the source image.
5. Do not add, remove, or reposition any element outside the white mask region.
```

---

### 4.2. Inpaint Suffix
* **File Location**: `src/app/prompts/inpaint_suffix.txt`
* **Target Model**: `gemini-3.1-flash-image`
* **Placeholders**: `{NEGATIVE_PROMPT}`
* **Full Verbatim Content**:

```text
Do not include: {NEGATIVE_PROMPT}. Do not change anything outside the white mask region.
```

---

### 4.3. Inpaint Record Prompt Formatter
* **Source Location**: `src/app/services/generation_service.py` (lines 1440, 1459)
* **Format**:
```python
compiled_prompt = f"[Inpaint Edit] {prompt.strip()}"
```

---

## 5. Step 4: Export Studio & AI Master Restoration

### 5.1. Default AI Upscale & Restoration Prompt
* **Source Location**: `src/app/services/export_service.py` (`DEFAULT_UPSCALE_PROMPT`)
* **Target Model**: `gemini-3.1-flash-lite-image` (via `/api/export/prepare` & `ExportService.prepare_export_master`)
* **Conditioning**: High-resolution image-to-image restoration conditioning with original seed lock.
* **Full Verbatim Content**:

```text
Restore, de-noise, and enhance the provided reference image as an authentic raw photo. Maximize optical resolution, fine film grain, and crisp focus while strictly preserving original facial structures, visible skin pores, natural skin texture, stray hairs, minor skin blemishes, natural light, and overall composition. Focus on ensuring that all clothing, garments, fabric weaves, seams, and material textures are clear, tactile, and richly detailed.
```

---

## 6. Frontend UI Prompts, Placeholders & Guiding Texts

The frontend user interface provides specific prompt guidance, placeholders, and tips across the user workflow:

### 6.1. Moodboard Ingestion (`src/frontend/src/components/MoodboardUploader.jsx`)
* **Prompt Label**: `Starting Scene Prompt *`
* **Textarea Placeholder**:
  ```text
  Enter the required starting scene direction, characters, mood, setting, lighting, and style overrides (e.g. 'A high-fashion editorial portrait in a sunlit modernist villa with tailored neutral wardrobe and warm film tones')...
  ```
* **Prompt Hint / Guidance**:
  ```text
  The AI Vision Director will synthesize your moodboard references together with this prompt to craft the optimal Master Prompt, 9-category visual levers, and 4 baseline candidates.
  ```

### 6.2. Refinement Chat (`src/frontend/src/components/RefinementChat.jsx`)
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

### 6.3. Canvas Studio Inpainting (`src/frontend/src/components/CanvasStudio.jsx`)
* **Prompt Input Placeholder**:
  ```text
  Describe only the change inside the painted region (e.g., 'replace with gold embroidery pattern and metallic sheen')...
  ```
* **Prompt Tips Callout**:
  - Focus strictly on the selected area (e.g. *"change the leather jacket to dark forest green suede"*).
  - Specify color, texture, material, and finish for crisp adjustments.
  - One specific change per iteration yields the cleanest preservation of the background.

---

## 7. Telemetry & Observability Auditing

Every prompt, template execution, and response across the life cycle is logged with structured telemetry:

1. **`storage/logs/vision_audit.jsonl`**:
   - `vision_request`: Logs the complete `instruction` (`extraction_system.txt`), user requirements, and reference moodboard image hashes.
   - `vision_response`: Logs the raw JSON response, extracted `master_prompt`, `narrative`, and category tag counts.
2. **`storage/logs/generation_audit.jsonl`**:
   - `baseline_single_request` / `baseline_batch_request`: Logs the compiled modular prompt, seed, aspect ratio, and negative prompt.
   - `refinement_request`: Logs the user prompt, wrapped `compiled_prompt` (`refinement_system.txt`), seed, and parent image hash.
   - `inpaint_request`: Logs the spatial inpaint prompt, mask metrics (pixel coverage percentage, bbox, centroid), and seed.
   - `export_prepare_started`: Logs the AI master raw photo restoration prompt and source generation ID.
3. **`storage/logs/wardrobe_audit.jsonl`**:
   - `wardrobe_segmentation_request`: Logs segmentation prompt and source sheet hash.
   - `wardrobe_grounding_request`: Logs dropped pin coordinates and subject grounding prompt.
   - `wardrobe_compose_request`: Logs multi-reference composition prompt and grounded subject lines.
