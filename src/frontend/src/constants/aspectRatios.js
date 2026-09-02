/**
 * Canonical Aspect Ratio Configurations and Resolutions for Google Imagen / Gemini.
 */

export const ASPECT_RATIO_OPTIONS = [
  { id: '1:1', label: '1:1', name: 'Square (1:1)', icon: 'square', desc: '3840×3840 4K Master Grid', width: 3840, height: 3840 },
  { id: '16:9', label: '16:9', name: 'Widescreen (16:9)', icon: 'horizontal', desc: '3840×2160 4K UHD', width: 3840, height: 2160 },
  { id: '9:16', label: '9:16', name: 'Vertical (9:16)', icon: 'vertical', desc: '2160×3840 4K Story / Reel', width: 2160, height: 3840 },
  { id: '21:9', label: '21:9', name: 'Cinema (21:9)', icon: 'horizontal', desc: '3840×1645 4K Ultrawide', width: 3840, height: 1645 },
  { id: '2:3', label: '2:3', name: 'Fashion (2:3)', icon: 'vertical', desc: '2560×3840 4K Editorial Portrait', width: 2560, height: 3840 },
  { id: '3:2', label: '3:2', name: 'Photo (3:2)', icon: 'horizontal', desc: '3840×2560 4K Landscape', width: 3840, height: 2560 },
  { id: '4:5', label: '4:5', name: 'Social (4:5)', icon: 'vertical', desc: '3072×3840 4K Social Portrait', width: 3072, height: 3840 },
  { id: '5:4', label: '5:4', name: 'Large Format (5:4)', icon: 'horizontal', desc: '3840×3072 4K Print', width: 3840, height: 3072 },
  { id: '3:4', label: '3:4', name: 'Portrait (3:4)', icon: 'vertical', desc: '2880×3840 4K Classic', width: 2880, height: 3840 },
  { id: '4:3', label: '4:3', name: 'Standard (4:3)', icon: 'horizontal', desc: '3840×2880 4K Classic', width: 3840, height: 2880 },
  { id: '1.8:1', label: '1.8:1', name: 'Cinematic (1.8:1)', icon: 'horizontal', desc: '3840×2133 4K Cinema', width: 3840, height: 2133 },
  { id: '1.85:1', label: '1.85:1', name: 'Theatrical (1.85:1)', icon: 'horizontal', desc: '3840×2075 DCI Widescreen', width: 3840, height: 2075 },
];

export const ASPECT_RATIO_PREVIEWS = {
  '1:1': { width: 1080, height: 1080 },
  '16:9': { width: 1920, height: 1080 },
  '9:16': { width: 1080, height: 1920 },
  '21:9': { width: 2560, height: 1080 },
  '2:3': { width: 1080, height: 1620 },
  '3:2': { width: 1620, height: 1080 },
  '4:5': { width: 1080, height: 1350 },
  '5:4': { width: 1350, height: 1080 },
  '3:4': { width: 1080, height: 1440 },
  '4:3': { width: 1440, height: 1080 },
  '1.8:1': { width: 1920, height: 1067 },
  '1.85:1': { width: 1998, height: 1080 },
};

export const ASPECT_RATIO_MASTERS = {
  '1:1': { width: 3840, height: 3840 },
  '16:9': { width: 3840, height: 2160 },
  '9:16': { width: 2160, height: 3840 },
  '21:9': { width: 3840, height: 1645 },
  '2:3': { width: 2560, height: 3840 },
  '3:2': { width: 3840, height: 2560 },
  '4:5': { width: 3072, height: 3840 },
  '5:4': { width: 3840, height: 3072 },
  '3:4': { width: 2880, height: 3840 },
  '4:3': { width: 3840, height: 2880 },
  '1.8:1': { width: 3840, height: 2133 },
  '1.85:1': { width: 3840, height: 2075 },
};

export function parseAspectRatio(aspectRatioStr) {
  if (!aspectRatioStr) {
    return {
      cssRatio: '1 / 1',
      ratioValue: 1.0,
      orientation: 'square',
      label: '1:1',
    };
  }

  let ratioValue = 1.0;
  let cssRatio = '1 / 1';
  const label = aspectRatioStr;

  if (aspectRatioStr.includes(':')) {
    const [wStr, hStr] = aspectRatioStr.split(':');
    const w = parseFloat(wStr);
    const h = parseFloat(hStr);
    if (!isNaN(w) && !isNaN(h) && h > 0) {
      ratioValue = w / h;
      cssRatio = `${w} / ${h}`;
    }
  } else {
    const val = parseFloat(aspectRatioStr);
    if (!isNaN(val) && val > 0) {
      ratioValue = val;
      cssRatio = `${val} / 1`;
    }
  }

  let orientation = 'square';
  if (ratioValue >= 0.95 && ratioValue <= 1.05) {
    orientation = 'square';
  } else if (ratioValue > 1.05) {
    orientation = 'horizontal';
  } else {
    orientation = 'vertical';
  }

  return {
    cssRatio,
    ratioValue,
    orientation,
    label,
  };
}

export function detectClosestRatio(width, height) {
  if (!width || !height || height <= 0) return '1:1';
  const targetRatio = width / height;
  const ratioValues = {
    '1:1': 1.0,
    '16:9': 16 / 9,
    '9:16': 9 / 16,
    '21:9': 21 / 9,
    '2:3': 2 / 3,
    '3:2': 3 / 2,
    '4:5': 4 / 5,
    '5:4': 5 / 4,
    '3:4': 3 / 4,
    '4:3': 4 / 3,
    '1.8:1': 1.8,
    '1.85:1': 1.85,
  };
  let bestMatch = '1:1';
  let minDiff = Infinity;
  for (const [key, val] of Object.entries(ratioValues)) {
    const diff = Math.abs(val - targetRatio);
    if (diff < minDiff) {
      minDiff = diff;
      bestMatch = key;
    }
  }
  return bestMatch;
}

export function getBaseResolution(aspectRatioStr) {
  return ASPECT_RATIO_PREVIEWS[aspectRatioStr] || { width: 1080, height: 1080 };
}

export function getMasterResolution(aspectRatioStr) {
  return ASPECT_RATIO_MASTERS[aspectRatioStr] || { width: 3840, height: 3840 };
}
