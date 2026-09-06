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
  narrative: '',
  categories: {
    subject_details: [],
    objects_props: [],
    wardrobe_hair: [],
    environment: [],
    layout_framing: [],
    lighting: [],
    color_profile: [],
    camera_optics: [],
    mood_era: [],
  },
  locked_categories: [],
};

