const CATEGORY_NAMES = {
  subject_details: 'Subject & Character Details',
  wardrobe_hair: 'Wardrobe & Hairstyle',
  objects_props: 'Objects & Key Props',
  environment: 'Environment & Setting',
  layout_framing: 'Layout & Framing',
  camera_optics: 'Camera & Optics',
  lighting: 'Lighting & Atmosphere',
  color_profile: 'Color Profile & Palette',
  mood_era: 'Mood, Vibe & Era',
  custom: 'Custom Tags',
};

export function extractCategoryLabels(cats, catKey) {
  if (!cats || !cats[catKey]) return [];
  const items = cats[catKey];
  const labels = [];
  for (const item of items) {
    if (typeof item === 'string' && item.trim()) {
      labels.push(item.trim());
    } else if (item && typeof item === 'object') {
      if (item.enabled === false) continue;
      const lbl = String(item.label || '').trim();
      if (lbl) {
        labels.push(lbl);
      }
    }
  }
  return labels;
}

/**
 * Detects which categories or narrative have changed between current state and baseline snapshot.
 */
export function getModifiedCategories(
  currentCategories = {},
  baselineCategories = {},
  currentNarrative = '',
  baselineNarrative = ''
) {
  const modified = {};
  const currentCats = currentCategories || {};
  const baseCats = baselineCategories || {};

  const allKeys = new Set([...Object.keys(currentCats), ...Object.keys(baseCats)]);
  for (const key of allKeys) {
    const currLabels = extractCategoryLabels(currentCats, key);
    const baseLabels = extractCategoryLabels(baseCats, key);

    if (currLabels.length !== baseLabels.length) {
      modified[key] = true;
    } else {
      const isDiff = currLabels.some((val, idx) => val !== baseLabels[idx]);
      if (isDiff) {
        modified[key] = true;
      }
    }
  }

  const narrativeModified = String(currentNarrative || '').trim() !== String(baselineNarrative || '').trim();

  return {
    categories: modified,
    narrative: narrativeModified,
    hasChanges: narrativeModified || Object.keys(modified).length > 0,
  };
}

/**
 * Compiles 9-category visual tags into a unified, high-fidelity prompt.
 * Supports both compileModularPrompt(categories, customTags, promptOverride) and legacy compileModularPrompt(narrative, categories, ...).
 */
export function compileModularPrompt(
  categoriesOrNarrative = {},
  customTagsOrCategories = [],
  promptOverrideOrCustomTags = null,
  promptOverride = null
) {
  let categories = {};
  let customTags = [];
  let override = null;
  let legacyNarrative = '';

  if (typeof categoriesOrNarrative === 'string') {
    // Legacy invocation: (narrative, categories, customTags, promptOverride)
    legacyNarrative = categoriesOrNarrative.trim();
    categories = customTagsOrCategories || {};
    customTags = Array.isArray(promptOverrideOrCustomTags) ? promptOverrideOrCustomTags : [];
    override = promptOverride;
  } else {
    // Standard invocation: (categories, customTags, promptOverride)
    categories = categoriesOrNarrative || {};
    customTags = Array.isArray(customTagsOrCategories) ? customTagsOrCategories : [];
    override = promptOverrideOrCustomTags;
  }

  if (override && typeof override === 'string' && override.trim()) {
    return override.trim();
  }

  const sections = [];
  if (legacyNarrative) {
    sections.push(legacyNarrative);
  }

  const cats = categories || {};
  const subjectLabels = extractCategoryLabels(cats, 'subject_details');
  const wardrobeLabels = extractCategoryLabels(cats, 'wardrobe_hair');
  const objectLabels = extractCategoryLabels(cats, 'objects_props');
  const envLabels = extractCategoryLabels(cats, 'environment');
  const framingLabels = extractCategoryLabels(cats, 'layout_framing');
  const cameraLabels = extractCategoryLabels(cats, 'camera_optics');
  const lightingLabels = extractCategoryLabels(cats, 'lighting');
  const colorLabels = extractCategoryLabels(cats, 'color_profile');
  const moodLabels = extractCategoryLabels(cats, 'mood_era');
  const customLabels = (customTags || []).map((t) => String(t).trim()).filter(Boolean);
  const customCatLabels = extractCategoryLabels(cats, 'custom');
  const allCustom = [...customLabels, ...customCatLabels];

  if (subjectLabels.length > 0 || wardrobeLabels.length > 0) {
    const parts = [];
    if (subjectLabels.length > 0) parts.push(subjectLabels.join(', '));
    if (wardrobeLabels.length > 0) parts.push(`wearing ${wardrobeLabels.join(', ')}`);
    sections.push(`Subject: ${parts.join(', ')}.`);
  }

  if (envLabels.length > 0 || objectLabels.length > 0) {
    const parts = [];
    if (envLabels.length > 0) parts.push(`set in ${envLabels.join(', ')}`);
    if (objectLabels.length > 0) parts.push(`featuring ${objectLabels.join(', ')}`);
    sections.push(`Environment: ${parts.join(', ')}.`);
  }

  if (framingLabels.length > 0 || cameraLabels.length > 0) {
    const parts = [];
    if (framingLabels.length > 0) parts.push(framingLabels.join(', '));
    if (cameraLabels.length > 0) parts.push(`shot on ${cameraLabels.join(', ')}`);
    sections.push(`Composition: ${parts.join(', ')}.`);
  }

  if (lightingLabels.length > 0 || colorLabels.length > 0) {
    const parts = [];
    if (lightingLabels.length > 0) parts.push(`illuminated with ${lightingLabels.join(', ')}`);
    if (colorLabels.length > 0) parts.push(`color palette of ${colorLabels.join(', ')}`);
    sections.push(`Lighting & Color: ${parts.join(', ')}.`);
  }

  if (moodLabels.length > 0) {
    sections.push(`Aesthetic: ${moodLabels.join(', ')}.`);
  }

  if (allCustom.length > 0) {
    sections.push(`Details: ${allCustom.join(', ')}.`);
  }

  const compiled = sections.join(' ').trim();
  return compiled || (legacyNarrative ? legacyNarrative : 'A high-fashion cinematic scene with exquisite detail.');
}

/**
 * Compiles an Image-to-Image Delta Prompt when fine-tuning from a baseline image reference.
 * Strictly preserves the base image's subject identity, composition, pose, and background
 * while directing targeted adjustments only to edited tags.
 */
export function compileDeltaPrompt({
  categories = {},
  baselineCategories = null,
  lockedCategories = [],
  customTags = [],
  promptOverride = null,
  narrative = '',
  baselineNarrative = '',
}) {
  if (promptOverride && promptOverride.trim()) {
    return promptOverride.trim();
  }

  // If no baseline categories provided, fall back to standard modular scene prompt
  if (!baselineCategories || typeof baselineCategories !== 'object') {
    return compileModularPrompt(categories, customTags, promptOverride);
  }

  const diff = getModifiedCategories(categories, baselineCategories, narrative, baselineNarrative);

  // If literally nothing was modified and narrative is unchanged
  if (!diff.hasChanges) {
    return `Visual Continuity: Faithfully preserve the character identity, pose, framing, and environment from the input reference image while subtly refining overall render fidelity and atmospheric coherence.`;
  }

  const sections = [];

  // 1. Visual Reference Foundation Directive
  sections.push(
    `Visual Reference Foundation: Use the reference image as the structural, character, and stylistic anchor. Maintain raw photo fidelity, 1:1 original source sharpness, visible skin pores, natural skin texture, realistic teeth texture, natural tooth alignment, authentic gum line, subtle dental translucency, minor skin blemishes, natural light, and natural micro-contrast. Apply the requested modifications below seamlessly, allowing all naturally interconnected visual elements—including lighting falloff, cast shadows, color bounce, material reactions, and environmental reflections—to adjust organically for realistic visual cohesion without waxy smoothing, artificial plastic finish, or compression degradation.`
  );

  // 2. Requested Modifications Section
  const adjustments = [];
  if (diff.narrative && narrative && narrative.trim()) {
    adjustments.push(`Scene Direction: ${narrative.trim()}`);
  }

  const cats = categories || {};

  if (diff.categories.subject_details) {
    const labels = extractCategoryLabels(cats, 'subject_details');
    if (labels.length > 0) adjustments.push(`Subject Details: ${labels.join(', ')}`);
  }

  if (diff.categories.wardrobe_hair) {
    const labels = extractCategoryLabels(cats, 'wardrobe_hair');
    if (labels.length > 0) adjustments.push(`Wardrobe & Hairstyle: wearing ${labels.join(', ')}`);
  }

  if (diff.categories.objects_props) {
    const labels = extractCategoryLabels(cats, 'objects_props');
    if (labels.length > 0) adjustments.push(`Objects & Props: featuring ${labels.join(', ')}`);
  }

  if (diff.categories.environment) {
    const labels = extractCategoryLabels(cats, 'environment');
    if (labels.length > 0) adjustments.push(`Environment: set in ${labels.join(', ')}`);
  }

  if (diff.categories.layout_framing) {
    const labels = extractCategoryLabels(cats, 'layout_framing');
    if (labels.length > 0) adjustments.push(`Framing & Layout: ${labels.join(', ')}`);
  }

  if (diff.categories.lighting) {
    const labels = extractCategoryLabels(cats, 'lighting');
    if (labels.length > 0) adjustments.push(`Lighting: illuminated with ${labels.join(', ')}`);
  }

  if (diff.categories.color_profile) {
    const labels = extractCategoryLabels(cats, 'color_profile');
    if (labels.length > 0) adjustments.push(`Color Profile: palette of ${labels.join(', ')}`);
  }

  if (diff.categories.camera_optics) {
    const labels = extractCategoryLabels(cats, 'camera_optics');
    if (labels.length > 0) adjustments.push(`Camera & Optics: shot on ${labels.join(', ')}`);
  }

  if (diff.categories.mood_era) {
    const labels = extractCategoryLabels(cats, 'mood_era');
    if (labels.length > 0) adjustments.push(`Aesthetic & Mood: ${labels.join(', ')}`);
  }

  if (diff.categories.custom) {
    const labels = extractCategoryLabels(cats, 'custom');
    if (labels.length > 0) adjustments.push(`Custom Details: ${labels.join(', ')}`);
  }

  if (adjustments.length > 0) {
    sections.push(`Requested Modifications: ${adjustments.join('. ')}.`);
  }

  // 3. Locked Categories Guardrail (Consistent Anchors)
  const allKnownCategories = [
    'subject_details',
    'wardrobe_hair',
    'objects_props',
    'environment',
    'layout_framing',
    'camera_optics',
    'lighting',
    'color_profile',
    'mood_era',
  ];

  const preservedCategoryNames = allKnownCategories
    .filter((k) => lockedCategories.includes(k))
    .map((k) => CATEGORY_NAMES[k] || k);

  if (preservedCategoryNames.length > 0) {
    sections.push(
      `Consistent Anchors: Maintain the core design, identity, and styling of ${preservedCategoryNames.join(
        ', '
      )}, while allowing them to interact realistically with the updated scene conditions.`
    );
  }

  return sections.join(' ').trim();
}

