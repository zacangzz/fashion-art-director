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

---

## Cloud Deployment, Containers & CI/CD

### 4. FastAPI Packaging in Multi-Stage Docker with `uv`
* **Python Path in Containers**: When code is organized under `src/app/`, Uvicorn requires `PYTHONPATH=/app/src` so `from app.config import get_settings` resolves cleanly:
  ```dockerfile
  ENV PYTHONPATH=/app/src
  CMD ["/app/.venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
  ```
* **Multi-Stage Build**: Use `node:22-alpine` for building frontend assets and copy `/build/dist` directly into `/app/src/frontend/dist` in the Python runtime stage.

---

### 5. Firebase Hosting CDN Rewrites to Cloud Run
* **Unified Same-Origin Routing**: Avoid CORS complexity by proxying `/api/**` to Cloud Run via Firebase Hosting edge rewrites in `firebase.json`:
  ```json
  {
    "hosting": {
      "public": "src/frontend/dist",
      "rewrites": [
        { "source": "/api/**", "run": { "serviceId": "fashion-art-director", "region": "asia-southeast1" } },
        { "source": "/health", "run": { "serviceId": "fashion-art-director", "region": "asia-southeast1" } },
        { "source": "**", "destination": "/index.html" }
      ]
    }
  }
  ```

---

### 6. Keyless CI/CD via Workload Identity Federation (WIF)
* **OIDC Provider Configuration**: When creating GitHub OIDC providers with `--attribute-mapping`, provide `--attribute-condition` matching the repository claim to satisfy GCP IAM security constraints:
  ```bash
  gcloud iam workload-identity-pools providers create-oidc "github-actions-provider" \
    --project="ai-art-director-prod" \
    --location="global" \
    --workload-identity-pool="github-actions-pool" \
    --issuer-uri="https://token.actions.githubusercontent.com" \
    --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
    --attribute-condition="assertion.repository == 'zacangzz/fashion-art-director'"
  ```
* **GitHub Actions Workflow**: Authenticate securely using `google-github-actions/auth@v2` without storing long-lived service account keys in repository secrets.

