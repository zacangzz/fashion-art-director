export const PROP_CATEGORIES = [
  'all',
  'furniture',
  'decor',
  'lighting',
  'tech',
  'vehicle',
  'nature',
  'tableware',
  'misc',
];

export const PROP_CATEGORY_COLORS = {
  furniture: '#6366f1',
  decor: '#14b8a6',
  lighting: '#f59e0b',
  tech: '#06b6d4',
  vehicle: '#ec4899',
  nature: '#10b981',
  tableware: '#8b5cf6',
  misc: '#64748b',
};

export const PROP_SCALE_PRESETS = [
  { id: 'small', label: 'Small Accent', factor: 0.15, description: 'Tabletop or handheld accent item' },
  { id: 'medium', label: 'Medium', factor: 0.30, description: 'Floor or seated human scale item' },
  { id: 'large', label: 'Large Dominant', factor: 0.55, description: 'Dominant room-scale furniture or vehicle' },
];
