# Lessons Learned & API Insights

## Google GenAI Interactions API (`client.interactions.create`)

### 1. Image Model Resolution Limits & 404 "Requested entity was not found"
* **`gemini-3.1-flash-lite-image` (Nano Banana 2 Lite)**:
  * **Supported resolutions**: Standard `1K` (or 512px / omitted `image_size`).
  * **Unsupported resolutions**: `2K` and `4K`.
  * **Gotcha**: Passing `image_size: "4K"` or `image_size: "2K"` in `response_format` when targeting `gemini-3.1-flash-lite-image` causes Google GenAI's API to return:
    ```
    404 - {'error': {'message': 'Requested entity was not found.', 'code': 'not_found'}}
    ```
    This error occurs not because the model itself is missing, but because the requested resolution entity/tier does not exist for the lite model family.
  * **Fix/Rule**: Always negotiate resolution based on model capability (`resolve_model_image_size`). For lite models, clamp `image_size` to `"1K"` or omit `image_size`.

* **`gemini-3.1-flash-image` (Nano Banana 2) & `gemini-3-pro-image` (Nano Banana Pro)**:
  * Fully support high-resolution generation with `image_size: "1K"`, `"2K"`, and `"4K"`.

---

### 2. Structured JSON Output (`response_format`)
* **NEVER** use `{"type": "json"}` in `response_format` (throws `400 Bad Request`).
* Always configure `type: "text"` with `mime_type: "application/json"`:
  ```python
  response_format={
      "type": "text",
      "mime_type": "application/json",
  }
  ```

---

### 3. Multi-Turn Image Conditioning & Color Drift Prevention
* **Lossy Chroma Subsampling Degradation**:
  * When chaining multi-turn image edits (e.g. progressive wardrobe styling), re-encoding reference images with lossy formats (like standard lossy WebP or JPEG at `quality=90`) uses $\text{YUV 4:2:0}$ chroma subsampling, which discards $75\%$ of color detail and introduces integer quantization error.
  * In iterative loops, this causes noticeable chromatic degradation and shifts midtones/shadows.
  * **Fix**: Always pass conditioning reference images to the API using **lossless PNG or lossless WebP** with $100\%$ chroma preservation.
* **Color Profile (ICC) Preservation**:
  * Default PIL `Image.save()` calls strip embedded ICC profiles unless explicitly copied (`icc_profile=pil_img.info.get('icc_profile')`).
  * Dropping ICC profiles causes wide-gamut images (Display P3, Adobe RGB) to be misinterpreted as uncalibrated sRGB, exaggerating red and magenta saturation.
  * **Fix**: Retain `icc_profile` across all reference optimization and master saving functions.
* **Generative Model Feedback Loops & Prompt Invariance Locks**:
  * Generative diffusion/autoregressive image models naturally bias slightly warm on skin and lighting. If prompts instruct the model to calculate unrestricted "ambient color bounce", each progressive turn compounds the warmth of the previous generation.
  * **Fix**: In multi-turn styling/editing system prompts, always include a **Color Constancy & Calibrated White Balance Lock** (locking Kelvin temperature, neutral white points, and background chromaticity), and trace lineage ancestry to anchor multi-turn generations ($\text{Turn} \ge 2$) to the pristine root baseline scene.

