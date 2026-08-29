export const CATEGORIES = [
  { key: 'subject_details', label: 'Subject & Character Details', color: '#06b6d4', icon: 'User' },
  { key: 'objects_props', label: 'Objects & Key Props', color: '#f97316', icon: 'Package' },
  { key: 'wardrobe_hair', label: 'Wardrobe & Hairstyle', color: '#ec4899', icon: 'Sparkles' },
  { key: 'environment', label: 'Environment & Setting', color: '#84cc16', icon: 'Compass' },
  { key: 'layout_framing', label: 'Layout & Framing', color: '#10b981', icon: 'Maximize2' },
  { key: 'lighting', label: 'Lighting & Atmosphere', color: '#f59e0b', icon: 'Sun' },
  { key: 'color_profile', label: 'Color Profile & Palette', color: '#e11d48', icon: 'Palette' },
  { key: 'camera_optics', label: 'Camera & Optical Specs', color: '#a855f7', icon: 'Camera' },
  { key: 'mood_era', label: 'Mood, Vibe & Era', color: '#3b82f6', icon: 'Clock' },
];

export const DEFAULT_TAG_STATE = {
  narrative: 'A striking editorial composition featuring authentic subject emotion and refined atmospheric styling.',
  categories: {
    subject_details: [
      { id: 'tag_sub_1', category: 'subject_details', label: 'striking expressive subject', enabled: true, locked: false, isCustom: false },
      { id: 'tag_sub_2', category: 'subject_details', label: 'natural authentic pose', enabled: true, locked: false, isCustom: false },
    ],
    objects_props: [
      { id: 'tag_obj_1', category: 'objects_props', label: 'curated designer furniture', enabled: true, locked: false, isCustom: false },
    ],
    wardrobe_hair: [
      { id: 'tag_wrd_1', category: 'wardrobe_hair', label: 'tailored contemporary wardrobe', enabled: true, locked: false, isCustom: false },
      { id: 'tag_wrd_2', category: 'wardrobe_hair', label: 'styled textured hair', enabled: true, locked: false, isCustom: false },
    ],
    environment: [
      { id: 'tag_env_1', category: 'environment', label: 'architectural spatial setting', enabled: true, locked: false, isCustom: false },
    ],
    layout_framing: [
      { id: 'tag_lay_1', category: 'layout_framing', label: 'cinematic medium shot', enabled: true, locked: false, isCustom: false },
      { id: 'tag_lay_2', category: 'layout_framing', label: 'balanced dynamic composition', enabled: true, locked: false, isCustom: false },
    ],
    lighting: [
      { id: 'tag_lit_1', category: 'lighting', label: 'natural directional sunlight', enabled: true, locked: false, isCustom: false },
      { id: 'tag_lit_2', category: 'lighting', label: 'soft ambient fill with gentle contrast', enabled: true, locked: false, isCustom: false },
    ],
    color_profile: [
      { id: 'tag_col_1', category: 'color_profile', label: 'warm harmonious color palette', enabled: true, locked: false, isCustom: false },
      { id: 'tag_col_2', category: 'color_profile', label: 'rich analog film tone', enabled: true, locked: false, isCustom: false },
    ],
    camera_optics: [
      { id: 'tag_cam_1', category: 'camera_optics', label: '35mm prime lens', enabled: true, locked: false, isCustom: false },
      { id: 'tag_cam_2', category: 'camera_optics', label: 'prime lens f/2.0', enabled: true, locked: false, isCustom: false },
    ],
    mood_era: [
      { id: 'tag_mod_1', category: 'mood_era', label: 'editorial luxury aesthetic', enabled: true, locked: false, isCustom: false },
      { id: 'tag_mod_2', category: 'mood_era', label: 'timeless candid vibe', enabled: true, locked: false, isCustom: false },
    ],
  },
  locked_categories: [],
};
