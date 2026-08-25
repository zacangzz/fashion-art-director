/**
 * Helper to parse and format descriptive error messages from API responses.
 * @param {Response} response
 * @param {string} defaultMessage
 * @returns {Promise<Object>}
 */
async function handleApiResponse(response, defaultMessage) {
  if (response.ok) {
    return response.json();
  }

  let errorDetail = '';
  try {
    const errorData = await response.json();
    errorDetail = errorData.detail || errorData.message || '';
  } catch {
    try {
      errorDetail = await response.text();
    } catch {
      errorDetail = '';
    }
  }

  if (response.status === 404) {
    throw new Error(
      errorDetail ||
        `Resource or API endpoint not found (404 Not Found). Please verify that the backend server is running on http://127.0.0.1:7860.`
    );
  }

  if (response.status === 502) {
    throw new Error(
      errorDetail ||
        `Backend gateway error (502): External service call failed. Verify your Google AI Studio API key and model availability in .env.`
    );
  }

  if (response.status === 401 || response.status === 403) {
    throw new Error(
      errorDetail ||
        `Authentication/Permission error (${response.status}): Check your GEMINI_API_KEY in .env.`
    );
  }

  throw new Error(
    errorDetail ||
      `${defaultMessage} (Status ${response.status}: ${response.statusText || 'Error'})`
  );
}

/**
 * Uploads 1-5 image files + optional text prompt for moodboard analysis & concurrent 4-baseline generation.
 * @param {File[]} files
 * @param {string} [prompt]
 * @param {string[]} [lockedSections]
 * @param {Object} [existingSchema]
 * @returns {Promise<{moodboard_id: string, schema: Object, baselines: Array}>}
 */
export async function analyzeAndGenerateBaselines(files, prompt = '', lockedSections = null, existingSchema = null) {
  const formData = new FormData();
  files.forEach((file) => {
    formData.append('files', file);
  });
  if (prompt && typeof prompt === 'string' && prompt.trim()) {
    formData.append('prompt', prompt.trim());
  }
  if (lockedSections && Array.isArray(lockedSections) && lockedSections.length > 0) {
    formData.append('locked_sections', JSON.stringify(lockedSections));
  }
  if (existingSchema && typeof existingSchema === 'object') {
    formData.append('existing_schema', JSON.stringify(existingSchema));
  }

  const response = await fetch('/api/moodboard/analyze-and-baselines', {
    method: 'POST',
    body: formData,
  });

  return handleApiResponse(response, 'Moodboard analysis and baseline generation failed');
}

/**
 * Uploads 1-5 image files + optional prompt for moodboard analysis (legacy).
 * @param {File[]} files
 * @param {string} [prompt]
 * @returns {Promise<{moodboard_id: string, extracted_chips: Array, extracted_json: Object}>}
 */
export async function analyzeMoodboard(files, prompt = '') {
  const formData = new FormData();
  files.forEach((file) => {
    formData.append('files', file);
  });
  if (prompt && typeof prompt === 'string' && prompt.trim()) {
    formData.append('prompt', prompt.trim());
  }

  const response = await fetch('/api/moodboard/analyze', {
    method: 'POST',
    body: formData,
  });

  return handleApiResponse(response, 'Moodboard analysis failed');
}

/**
 * Sends fine-tune re-generation request with seed locking & image reference.
 * @param {Object} payload { parent_id, schema, seed_mode, seed, use_image_reference, aspect_ratio, negative_prompt }
 * @returns {Promise<{generation_id: string, parent_id: string, seed: number, compiled_prompt: string, negative_prompt: string, image_url: string, created_at: string}>}
 */
export async function fineTuneGeneration(payload) {
  const response = await fetch('/api/generate/fine-tune', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  return handleApiResponse(response, 'Fine-tune generation failed');
}

/**
 * Fetches all past generation history records with lineage.
 * @returns {Promise<{generations: Array}>}
 */
export async function fetchHistory() {
  const response = await fetch('/api/history');
  return handleApiResponse(response, 'Failed to fetch history');
}

/**
 * Fetches single generation record by ID.
 * @param {string} id
 * @returns {Promise<Object>}
 */
export async function fetchGeneration(id) {
  const response = await fetch(`/api/generations/${id}`);
  return handleApiResponse(response, 'Failed to fetch generation');
}

/**
 * Fetches lineage graph for a given generation ID.
 * @param {string} id
 * @returns {Promise<{root_id: string, ancestors: Array, descendants: Array}>}
 */
export async function fetchLineage(id) {
  const response = await fetch(`/api/generations/${id}/lineage`);
  return handleApiResponse(response, 'Failed to fetch lineage');
}

/**
 * Restores studio workspace state from a past generation ID.
 * @param {string} id
 * @returns {Promise<Object>}
 */
export async function restoreGeneration(id) {
  const response = await fetch(`/api/generations/${id}/restore`, {
    method: 'POST',
  });
  return handleApiResponse(response, 'Failed to restore generation');
}

/**
 * Requests ZIP bundle export for a given generation ID.
 * @param {string} generationId
 * @returns {Promise<Blob>}
 */
export async function exportBundle(generationId) {
  const response = await fetch('/api/export/bundle', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ generation_id: generationId }),
  });

  if (!response.ok) {
    let errorDetail = '';
    try {
      const errorData = await response.json();
      errorDetail = errorData.detail || errorData.message || '';
    } catch {
      errorDetail = `Status ${response.status}: ${response.statusText}`;
    }
    throw new Error(errorDetail || 'Export bundle failed');
  }

  return response.blob();
}

/**
 * Canvas Studio: Sends inpaint request with source image blob, mask blob, prompt and optional generation_id/seed.
 * @param {Object} params { generationId, imageBlob, maskBlob, prompt, negativePrompt, seed }
 * @returns {Promise<{generation_id: string, parent_id: string, image_url: string, created_at: string, compiled_prompt: string, seed: number, resolution: Object}>}
 */
export async function inpaintRegion({ generationId, imageBlob, maskBlob, prompt, negativePrompt = null, seed = null }) {
  const formData = new FormData();
  if (generationId) {
    formData.append('generation_id', generationId);
  }
  formData.append('image', imageBlob, 'image.png');
  formData.append('mask', maskBlob, 'mask.png');
  formData.append('prompt', prompt);
  if (negativePrompt) {
    formData.append('negative_prompt', negativePrompt);
  }
  if (seed !== null && seed !== undefined) {
    formData.append('seed', seed);
  }

  const response = await fetch('/api/inpaint', {
    method: 'POST',
    body: formData,
  });

  return handleApiResponse(response, 'Canvas Studio inpainting failed');
}

/**
 * Legacy generation helper.
 * @param {Object} payload
 * @returns {Promise<Object>}
 */
export async function generateImage(payload) {
  const response = await fetch('/api/generate', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  return handleApiResponse(response, 'Generation failed');
}

