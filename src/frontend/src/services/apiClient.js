import { auth } from '../config/firebase';

/**
 * Enhanced fetch wrapper that attaches Firebase ID token if user is signed in.
 */
async function authFetch(url, options = {}) {
  const headers = new Headers(options.headers || {});

  try {
    if (auth && auth.currentUser) {
      const token = await auth.currentUser.getIdToken();
      if (token) {
        headers.set('Authorization', `Bearer ${token}`);
      }
    } else if (localStorage.getItem('dev_bypass_auth') === 'true') {
      headers.set('Authorization', 'Bearer local_dev_token');
    }
  } catch (err) {
    console.warn('Failed to retrieve auth token for request:', err);
  }

  return fetch(url, {
    ...options,
    headers,
  });
}

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

  if (response.status === 401) {
    throw new Error(
      errorDetail ||
        'Authentication required: Please sign in via the top navigation bar to access the studio.'
    );
  }

  if (response.status === 403) {
    throw new Error(
      errorDetail ||
        'Access Forbidden (403): You do not have permission to perform this action or access this resource.'
    );
  }

  throw new Error(
    errorDetail ||
      `${defaultMessage} (Status ${response.status}: ${response.statusText || 'Error'})`
  );
}

/**
 * Fetches model configuration including available vision & imagen models and server defaults.
 * @returns {Promise<{available_vision_models: string[], available_imagen_models: string[], default_vision_model: string, default_imagen_model: string, inpaint_model: string}>}
 */
export async function fetchModelConfig() {
  const response = await authFetch('/api/models/config');
  return handleApiResponse(response, 'Failed to fetch model configuration');
}

/**
 * Uploads 1-5 image files + optional text prompt for moodboard analysis & concurrent 4-baseline generation.
 * @param {File[]} files
 * @param {string} [prompt]
 * @param {string[]} [lockedSections]
 * @param {Object} [existingSchema]
 * @param {string} [aspectRatio]
 * @param {string} [visionModel]
 * @param {string} [imagenModel]
 * @returns {Promise<{moodboard_id: string, schema: Object, baselines: Array}>}
 */
export async function analyzeAndGenerateBaselines(
  files,
  prompt = '',
  lockedSections = null,
  existingSchema = null,
  aspectRatio = '1.8:1',
  visionModel = null,
  imagenModel = null
) {
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
  if (aspectRatio && typeof aspectRatio === 'string') {
    formData.append('aspect_ratio', aspectRatio);
  }
  if (visionModel) {
    formData.append('vision_model', visionModel);
  }
  if (imagenModel) {
    formData.append('imagen_model', imagenModel);
  }

  const response = await authFetch('/api/moodboard/analyze-and-baselines', {
    method: 'POST',
    body: formData,
  });

  return handleApiResponse(response, 'Moodboard analysis and baseline generation failed');
}

/**
 * Uploads a single photo to skip Step 1 Art Direction and start refinement directly.
 * @param {File} file
 * @param {string} [aspectRatio]
 * @returns {Promise<{generation_id: string, image_url: string, seed: number, aspect_ratio: string, resolution: Object, compiled_prompt: string, created_at: string}>}
 */
export async function uploadDirectPhoto(file, aspectRatio = null) {
  const formData = new FormData();
  formData.append('file', file);
  if (aspectRatio && typeof aspectRatio === 'string') {
    formData.append('aspect_ratio', aspectRatio);
  }

  const response = await authFetch('/api/moodboard/upload-direct-photo', {
    method: 'POST',
    body: formData,
  });

  return handleApiResponse(response, 'Direct photo upload failed');
}


/**
 * Uploads 1-5 image files + optional prompt for moodboard analysis (Step 1A).
 * Extracts Master Prompt, Narrative, and 9-category visual levers without generating images.
 * @param {File[]} files
 * @param {string} [prompt]
 * @param {string[]} [lockedCategories]
 * @param {Object} [existingSchema]
 * @param {string} [aspectRatio]
 * @param {string} [visionModel]
 * @returns {Promise<{moodboard_id: string, master_prompt: string, narrative: string, categories: Object, schema_data: Object}>}
 */
export async function analyzeMoodboard(
  files,
  prompt = '',
  lockedCategories = null,
  existingSchema = null,
  aspectRatio = '1.8:1',
  visionModel = null
) {
  const formData = new FormData();
  files.forEach((file) => {
    formData.append('files', file);
  });
  if (prompt && typeof prompt === 'string' && prompt.trim()) {
    formData.append('prompt', prompt.trim());
  }
  if (lockedCategories && Array.isArray(lockedCategories) && lockedCategories.length > 0) {
    formData.append('locked_categories', JSON.stringify(lockedCategories));
  }
  if (existingSchema && typeof existingSchema === 'object') {
    formData.append('existing_schema', JSON.stringify(existingSchema));
  }
  if (aspectRatio && typeof aspectRatio === 'string') {
    formData.append('aspect_ratio', aspectRatio);
  }
  if (visionModel) {
    formData.append('vision_model', visionModel);
  }

  const response = await authFetch('/api/moodboard/analyze', {
    method: 'POST',
    body: formData,
  });

  return handleApiResponse(response, 'Moodboard vision analysis failed');
}

/**
 * Spawns 4 concurrent baseline image candidate generations from customized Master Prompt (Step 1B).
 * @param {Object} payload { moodboard_id, master_prompt, narrative, categories, aspect_ratio, prompt_override, imagen_model }
 * @returns {Promise<{moodboard_id: string, baselines: Array}>}
 */
export async function generateBaselines(payload) {
  const response = await authFetch('/api/moodboard/generate-baselines', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  return handleApiResponse(response, 'Baseline candidate generation failed');
}

/**
 * Re-synthesizes fluid directorial Master Prompt prose from user-updated visual levers on demand.
 * @param {Object} payload { narrative, categories, previous_master_prompt, vision_model }
 * @returns {Promise<{master_prompt: string, narrative: string, conflicts: Array}>}
 */
export async function resyncPromptFromLevers(payload) {
  const response = await authFetch('/api/moodboard/resync-prompt', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  return handleApiResponse(response, 'Master prompt re-sync from levers failed');
}

/**
 * Deconstructs and extracts fine-grained 9-category visual levers from a user's Master Generation Prompt.
 * @param {Object} payload { master_prompt, narrative, categories, vision_model }
 * @returns {Promise<{categories: Object, narrative: string, conflicts: Array}>}
 */
export async function resyncLeversFromPrompt(payload) {
  const response = await authFetch('/api/moodboard/resync-levers', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  return handleApiResponse(response, 'Visual levers extraction from prompt failed');
}

/**
 * Backward-compatible alias for resyncPromptFromLevers.
 */
export const resyncMasterPrompt = resyncPromptFromLevers;

/**
 * Scans Master Prompt and visual levers for conflicting or contradictory directives.
 * @param {Object} payload { master_prompt, narrative, categories, vision_model }
 * @returns {Promise<{conflicts: Array}>}
 */
export async function checkPromptConflicts(payload) {
  const response = await authFetch('/api/moodboard/check-conflicts', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  return handleApiResponse(response, 'Prompt conflict check failed');
}

/**
 * Sends fine-tune re-generation request with seed locking & image reference.
 * @param {Object} payload { parent_id, schema, seed_mode, seed, use_image_reference, aspect_ratio, negative_prompt }
 * @returns {Promise<{generation_id: string, parent_id: string, seed: number, compiled_prompt: string, negative_prompt: string, image_url: string, created_at: string}>}
 */
export async function fineTuneGeneration(payload) {
  const response = await authFetch('/api/generate/fine-tune', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  return handleApiResponse(response, 'Fine-tune generation failed');
}

/**
 * Sends conversation-based refinement request with reference image & seed locking.
 * @param {Object} payload { parent_id, prompt, seed, seed_mode, aspect_ratio, negative_prompt, conversation_id }
 * @returns {Promise<{generation_id: string, parent_id: string, seed: number, compiled_prompt: string, image_url: string, created_at: string, resolution: Object, conversation_id: string}>}
 */
export async function refineGeneration(payload) {
  const response = await authFetch('/api/refine', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  return handleApiResponse(response, 'Refinement generation failed');
}

/**
 * Uploads a reference background image for multimodal background harmonization.
 * @param {File} file
 * @returns {Promise<{id: string, image_url: string, thumbnail_url: string, original_filename: string, aspect_ratio: string, created_at: string}>}
 */
export async function uploadBackgroundReference(file) {
  const formData = new FormData();
  formData.append('file', file);

  const response = await authFetch('/api/backgrounds/upload', {
    method: 'POST',
    body: formData,
  });

  return handleApiResponse(response, 'Failed to upload background reference');
}

/**
 * Fetches user's stored reusable background references.
 * @param {number} [limit=50]
 * @returns {Promise<{items: Array, total: number}>}
 */
export async function fetchBackgroundReferences(limit = 50) {
  const response = await authFetch(`/api/backgrounds?limit=${limit}`);
  return handleApiResponse(response, 'Failed to fetch background references');
}

/**
 * Deletes a stored background reference.
 * @param {string} bgId
 * @returns {Promise<{status: string, id: string}>}
 */
export async function deleteBackgroundReference(bgId) {
  const response = await authFetch(`/api/backgrounds/${bgId}`, {
    method: 'DELETE',
  });
  return handleApiResponse(response, 'Failed to delete background reference');
}

/**
 * Fetches conversation history thread by ID.
 * @param {string} conversationId
 * @returns {Promise<{conversation_id: string, baseline_generation_id: string, messages: Array}>}
 */
export async function fetchConversation(conversationId) {
  const response = await authFetch(`/api/conversations/${conversationId}`);
  return handleApiResponse(response, 'Failed to fetch conversation history');
}

/**
 * Fetches all past generation history records with lineage.
 * @returns {Promise<{generations: Array}>}
 */
export async function fetchHistory() {
  const response = await authFetch('/api/history');
  return handleApiResponse(response, 'Failed to fetch history');
}

/**
 * Fetches single generation record by ID.
 * @param {string} id
 * @returns {Promise<Object>}
 */
export async function fetchGeneration(id) {
  const response = await authFetch(`/api/generations/${id}`);
  return handleApiResponse(response, 'Failed to fetch generation');
}

/**
 * Fetches lineage graph for a given generation ID.
 * @param {string} id
 * @returns {Promise<{root_id: string, ancestors: Array, descendants: Array}>}
 */
export async function fetchLineage(id) {
  const response = await authFetch(`/api/generations/${id}/lineage`);
  return handleApiResponse(response, 'Failed to fetch lineage');
}

/**
 * Restores studio workspace state from a past generation ID.
 * @param {string} id
 * @returns {Promise<Object>}
 */
export async function restoreGeneration(id) {
  const response = await authFetch(`/api/generations/${id}/restore`, {
    method: 'POST',
  });
  return handleApiResponse(response, 'Failed to restore generation');
}

/**
 * Prepares high-quality master export by running Gemini image restoration and upscaling.
 * @param {string} generationId
 * @param {string} [promptOverride]
 * @returns {Promise<{generation_id: string, parent_id: string, master_image_url: string, aspect_ratio: string, resolution: Object, created_at: string, seed: number, compiled_prompt: string}>}
 */
export async function prepareExport(generationId, promptOverride = null) {
  const payload = { generation_id: generationId };
  if (promptOverride && typeof promptOverride === 'string' && promptOverride.trim()) {
    payload.prompt_override = promptOverride.trim();
  }
  const response = await authFetch('/api/export/prepare', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  return handleApiResponse(response, 'Failed to prepare export master');
}

/**
 * Requests ZIP bundle export for a given generation ID.
 * @param {string} generationId
 * @returns {Promise<Blob>}
 */
export async function exportBundle(generationId) {
  const response = await authFetch('/api/export/bundle', {
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
 * Canvas Studio: Sends inpaint request with source image blob, mask blob, prompt and optional generation_id/seed/aspectRatio.
 * @param {Object} params { generationId, imageBlob, maskBlob, prompt, negativePrompt, seed, aspectRatio }
 * @returns {Promise<{generation_id: string, parent_id: string, image_url: string, created_at: string, compiled_prompt: string, seed: number, aspect_ratio: string, resolution: Object}>}
 */
export async function inpaintRegion({ generationId, imageBlob, maskBlob, prompt, negativePrompt = null, seed = null, aspectRatio = null }) {
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
  if (aspectRatio && typeof aspectRatio === 'string') {
    formData.append('aspect_ratio', aspectRatio);
  }

  const response = await authFetch('/api/inpaint', {
    method: 'POST',
    body: formData,
  });

  return handleApiResponse(response, 'Canvas Studio inpainting failed');
}

export async function generateImage(payload) {
  const response = await authFetch('/api/generate', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  return handleApiResponse(response, 'Generation failed');
}

/**
 * Uploads a multi-garment lookbook sheet and auto-segments it into cards.
 * @param {File} file
 * @param {string} [visionModel]
 * @returns {Promise<{items: Array}>}
 */
export async function uploadWardrobeSheet(file, visionModel = null) {
  const formData = new FormData();
  formData.append('file', file);
  if (visionModel) {
    formData.append('vision_model', visionModel);
  }

  const response = await authFetch('/api/wardrobe/upload', {
    method: 'POST',
    body: formData,
  });

  return handleApiResponse(response, 'Wardrobe sheet segmentation failed');
}

/**
 * Fetches all saved wardrobe garment items for user.
 * @returns {Promise<{items: Array}>}
 */
export async function fetchWardrobeItems() {
  const response = await authFetch('/api/wardrobe/items');
  return handleApiResponse(response, 'Failed to fetch wardrobe items');
}

/**
 * Deletes a wardrobe item by ID.
 * @param {string} id
 * @returns {Promise<{status: string, id: string}>}
 */
export async function deleteWardrobeItem(id) {
  const response = await authFetch(`/api/wardrobe/items/${id}`, {
    method: 'DELETE',
  });
  return handleApiResponse(response, 'Failed to delete wardrobe item');
}

/**
 * Deletes all wardrobe items for the current user.
 * @returns {Promise<{status: string, deleted_count: number}>}
 */
export async function deleteAllWardrobeItems() {
  const response = await authFetch('/api/wardrobe/items', {
    method: 'DELETE',
  });
  return handleApiResponse(response, 'Failed to clear wardrobe items');
}

/**
 * Upscales a garment item to 4K definition.
 * @param {string} itemId
 * @param {Object} [options]
 * @returns {Promise<Object>}
 */
export async function upscaleGarment(itemId, { imagenModel } = {}) {
  const response = await authFetch(`/api/wardrobe/items/${encodeURIComponent(itemId)}/upscale`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ imagen_model: imagenModel }),
  });
  return handleApiResponse(response, 'Failed to upscale garment');
}

/**
 * Creates or updates a manual cropped garment item in wardrobe.
 * @param {Object} itemData
 * @returns {Promise<Object>}
 */
export async function createWardrobeItem(itemData) {
  const response = await authFetch('/api/wardrobe/items', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(itemData),
  });
  return handleApiResponse(response, 'Failed to save wardrobe item');
}

/**
 * Sends a vision region detection request to find subject/clothing bounding boxes.
 * @param {string} generationId
 * @param {string} [visionModel]
 * @returns {Promise<{regions: Array, image_url: string}>}
 */
export async function detectClothingRegions(generationId, visionModel = null) {
  const payload = { generation_id: generationId };
  if (visionModel) {
    payload.vision_model = visionModel;
  }
  const response = await authFetch('/api/wardrobe/detect-regions', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  return handleApiResponse(response, 'Failed to detect clothing regions');
}

/**
 * Sends a multi-image wardrobe composition request.
 * @param {Object} payload { parent_id, assignments, seed, seed_mode, aspect_ratio, negative_prompt, conversation_id, custom_instruction }
 * @returns {Promise<Object>}
 */
export async function composeWardrobe(payload) {
  const response = await authFetch('/api/wardrobe/compose', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  return handleApiResponse(response, 'Wardrobe composition failed');
}

/**
 * Fetches structured audit events with optional filtering.
 * @param {Object} [params]
 * @returns {Promise<{total: number, limit: number, offset: number, events: Array}>}
 */
export async function fetchTelemetryEvents({ component, event, requestId, status, search, limit = 50, offset = 0 } = {}) {
  const query = new URLSearchParams();
  if (component) query.set('component', component);
  if (event) query.set('event', event);
  if (requestId) query.set('request_id', requestId);
  if (status) query.set('status', status);
  if (search) query.set('search', search);
  query.set('limit', String(limit));
  query.set('offset', String(offset));

  const response = await authFetch(`/api/telemetry/events?${query.toString()}`);
  return handleApiResponse(response, 'Failed to fetch telemetry events');
}

/**
 * Fetches grouped end-to-end generation runs with stage events, prompts, and metrics.
 * @param {Object} [params]
 * @returns {Promise<{total: number, limit: number, offset: number, runs: Array}>}
 */
export async function fetchGenerationRuns({ component, status, search, limit = 50, offset = 0 } = {}) {
  const query = new URLSearchParams();
  if (component && component !== 'all') query.set('component', component);
  if (status && status !== 'all') query.set('status', status);
  if (search && search.trim()) query.set('search', search.trim());
  query.set('limit', String(limit));
  query.set('offset', String(offset));

  const response = await authFetch(`/api/telemetry/runs?${query.toString()}`);
  return handleApiResponse(response, 'Failed to fetch generation runs');
}

/**
 * Fetches the complete chronological trace of events for a request ID.
 * @param {string} requestId
 * @returns {Promise<Array>}
 */
export async function fetchRequestTrace(requestId) {
  const response = await authFetch(`/api/telemetry/events/${encodeURIComponent(requestId)}`);
  return handleApiResponse(response, `Failed to fetch trace for request ${requestId}`);
}

/**
 * Fetches summary statistics across stored telemetry events.
 * @returns {Promise<Object>}
 */
export async function fetchTelemetryStats() {
  const response = await authFetch('/api/telemetry/stats');
  return handleApiResponse(response, 'Failed to fetch telemetry statistics');
}

/**
 * Fetches recent application log lines.
 * @param {Object} [params]
 * @returns {Promise<{total_lines: number, logs: string[]}>}
 */
export async function fetchSystemLogs({ lines = 200, level } = {}) {
  const query = new URLSearchParams();
  query.set('lines', String(lines));
  if (level) query.set('level', level);

  const response = await authFetch(`/api/telemetry/logs?${query.toString()}`);
  return handleApiResponse(response, 'Failed to fetch system logs');
}

/**
 * Fetches Firestore database collections summary with document counts.
 * @returns {Promise<{tables: Object}>}
 */
export async function fetchDatabaseSummary() {
  const response = await authFetch('/api/telemetry/db/summary');
  return handleApiResponse(response, 'Failed to fetch database summary');
}

/**
 * Fetches paginated records for a Firestore database collection.
 * @param {string} tableName
 * @param {Object} [params]
 * @returns {Promise<{table: string, total: number, limit: number, offset: number, rows: Array}>}
 */
export async function fetchDatabaseTableRecords(tableName, { limit = 50, offset = 0 } = {}) {
  const query = new URLSearchParams();
  query.set('limit', String(limit));
  query.set('offset', String(offset));

  const response = await authFetch(`/api/telemetry/db/${encodeURIComponent(tableName)}?${query.toString()}`);
  return handleApiResponse(response, `Failed to fetch records for collection ${tableName}`);
}

/**
 * Fetches the authenticated user's profile and approval status from the backend.
 * @returns {Promise<{id: string, uid: string, email: string, display_name: string, photo_url: string, role: string, status: string, is_approved: boolean, is_admin: boolean, total_spend_usd: number, total_tokens: number}>}
 */
export async function fetchCurrentUserProfile() {
  const response = await authFetch('/api/auth/me');
  return handleApiResponse(response, 'Failed to fetch user authentication profile');
}

/**
 * (Admin only) Fetches the studio user list, pending invitations, and spend metrics.
 * @returns {Promise<{users: Array, summary: Object}>}
 */
export async function fetchAdminUsersList() {
  const response = await authFetch('/api/auth/users');
  return handleApiResponse(response, 'Failed to fetch authorized studio users');
}

/**
 * (Admin only) Pre-authorizes / invites an email to the studio whitelist.
 * @param {string} email
 * @param {string} [role='user']
 * @returns {Promise<{status: string, message: string, user: Object}>}
 */
export async function inviteUser(email, role = 'user') {
  const response = await authFetch('/api/auth/invite', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, role }),
  });
  return handleApiResponse(response, `Failed to pre-authorize user ${email}`);
}

/**
 * (Admin only) Updates a user's approval status or role.
 * @param {string} userId
 * @param {Object} updates
 * @returns {Promise<{status: string, message: string, user: Object}>}
 */
export async function updateUserStatus(userId, { status, role } = {}) {
  const response = await authFetch(`/api/auth/users/${encodeURIComponent(userId)}/status`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status, role }),
  });
  return handleApiResponse(response, `Failed to update user status for ${userId}`);
}

/**
 * (Admin only) Deletes / revokes a user invitation or account from the whitelist.
 * @param {string} userId
 * @returns {Promise<{status: string, message: string}>}
 */
export async function deleteUser(userId) {
  const response = await authFetch(`/api/auth/users/${encodeURIComponent(userId)}`, {
    method: 'DELETE',
  });
  return handleApiResponse(response, `Failed to delete user ${userId}`);
}

