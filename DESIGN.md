# Fashion Art Director Studio — Design System (`DESIGN.md`)

## 1. Brand Essence & Visual Language
**Fashion Art Director Studio** is a high-end, generative AI creative suite built for creative directors, fashion houses, and editorial stylists. The visual language blends obsidian minimalism, editorial typography, and vibrant electric neon accents that evoke haute couture digital craft.

### Core Visual Principles
1. **Editorial Luxury**: Deep obsidian backdrops with subtle atmospheric glow radial gradients.
2. **Glass & Depth**: Multi-layered backdrop blurs (`backdrop-filter: blur(14px)`), 1px semi-transparent borders, and soft glowing accent drop-shadows.
3. **Information Hierarchy**: Crisp typographic contrast between UI labels (`Inter`) and technical metadata/seeds/aspect ratios (`JetBrains Mono`).
4. **Fluid Responsiveness**: Resilient CSS grid and flex layouts adapting across 1024px to 1920px+ viewports with smooth micro-interactions.

---

## 2. Color Palette & Design Tokens

### Surface & Neutral Tones
- **`--bg-dark`**: `#07090e` (Deepest canvas background)
- **`--bg-surface`**: `#10141e` (Primary card/panel surface)
- **`--bg-surface-elevated`**: `#171d2b` (Elevated modals, toolbars, popovers)
- **`--bg-surface-hover`**: `#20283b` (Interactive item hover state)
- **`--bg-surface-active`**: `#2a344d` (Active/selected item state)
- **`--border-color`**: `rgba(255, 255, 255, 0.08)` (Subtle divider border)
- **`--border-color-hover`**: `rgba(255, 255, 255, 0.16)` (Elevated border on focus/hover)
- **`--border-focus`**: `#6366f1` (Active focus ring border)

### Typography Colors
- **`--text-primary`**: `#f8fafc` (Headings, primary values, active labels)
- **`--text-secondary`**: `#94a3b8` (Subtitles, metadata, secondary labels)
- **`--text-muted`**: `#64748b` (Disabled text, hints, placeholders)
- **`--text-inverse`**: `#07090e` (Text over high-contrast white/accent buttons)

### Accent & Semantic Ramps
- **Brand Violet / Primary**:
  - Main: `#6366f1` (Electric Indigo)
  - Hover: `#4f46e5`
  - Glow: `rgba(99, 102, 241, 0.35)`
  - Soft Background: `rgba(99, 102, 241, 0.12)`
- **Creative Magenta / Secondary**:
  - Main: `#a855f7` (Fashion Purple)
  - Hover: `#9333ea`
  - Soft Background: `rgba(168, 85, 247, 0.12)`
- **Cyan / Vision & Analysis**:
  - Main: `#06b6d4`
  - Soft Background: `rgba(6, 182, 212, 0.12)`
- **Emerald / Direct & Success**:
  - Main: `#10b981`
  - Soft Background: `rgba(168, 85, 129, 0.12)`
- **Amber / Warning & Seeds**:
  - Main: `#f59e0b`
  - Soft Background: `rgba(245, 158, 11, 0.12)`
- **Rose / Danger & Conflicts**:
  - Main: `#ef4444`
  - Soft Background: `rgba(239, 68, 68, 0.12)`

---

## 3. Typography Scale

- **Font Sans**: `'Inter', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif`
- **Font Mono**: `'JetBrains Mono', 'Fira Code', ui-monospace, SFMono-Regular, monospace`

| Scale | Size | Line Height | Weight | Usage |
|---|---|---|---|---|
| **Display** | `1.5rem` (24px) | `1.2` | 700 / Bold | Page & Section Titles |
| **Heading** | `1.15rem` (18.4px) | `1.3` | 600 / Semi-Bold | Card headers, Modal titles |
| **Subheading** | `0.95rem` (15.2px) | `1.4` | 600 / Semi-Bold | Group titles, drawer headers |
| **Body** | `0.85rem` (13.6px) | `1.5` | 400 / Regular | Chat messages, descriptions |
| **Body Bold** | `0.85rem` (13.6px) | `1.5` | 600 / Semi-Bold | Active items, buttons |
| **Caption** | `0.75rem` (12px) | `1.4` | 500 / Medium | Badges, step counters, input hints |
| **Micro / Mono** | `0.68rem` (10.8px) | `1.3` | 600 / Bold | Generation IDs, resolutions, seeds |

---

## 4. Elevation, Radii & Shadows

### Border Radii
- `--radius-xs`: `4px` (Tags, micro-chips)
- `--radius-sm`: `6px` (Buttons, inputs, small tooltips)
- `--radius-md`: `10px` (Cards, image previews, panels)
- `--radius-lg`: `16px` (Modals, drawers, main stage viewports)
- `--radius-xl`: `24px` (Hero banners, containers)
- `--radius-pill`: `9999px` (Pill buttons, status badges, step navigators)

### Shadows & Atmosphere
- `--shadow-card`: `0 8px 32px rgba(0, 0, 0, 0.45)`
- `--shadow-modal`: `0 24px 64px rgba(0, 0, 0, 0.75), 0 0 0 1px rgba(255, 255, 255, 0.08)`
- `--shadow-glow-primary`: `0 0 20px rgba(99, 102, 241, 0.35)`
- `--shadow-glow-cyan`: `0 0 20px rgba(6, 182, 212, 0.35)`
- `--shadow-glow-emerald`: `0 0 20px rgba(16, 185, 129, 0.35)`

---

## 5. UI Component Primitives Specs

### Buttons (`<Button>`)
- **Primary**: Gradient `linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)`, white text, glow on hover, active depression.
- **Secondary**: `var(--bg-surface-elevated)` background, 1px border `rgba(255,255,255,0.08)`, hover border `rgba(255,255,255,0.2)`.
- **Accent Emerald / Direct**: Gradient `linear-gradient(135deg, #10b981 0%, #06b6d4 100%)`.
- **Ghost**: Transparent background, text secondary, hover background `rgba(255,255,255,0.06)`.
- **Danger**: Red soft background `rgba(239, 68, 68, 0.15)`, red border & text, hover solid red.

### Modals (`<Modal>`)
- Accessible dialog overlay (`position: fixed; inset: 0; background: rgba(0,0,0,0.7); backdrop-filter: blur(8px)`).
- Esc key dismiss + backdrop click to close + body scroll lock.
- Clean header with title, subtitle, icon, close button.
- Flexible body with scroll overflow.
- Optional action footer.

### Badges & Chips (`<Badge>`)
- Semantic colors with 1px border and pill shape.
- Optional pulsing indicator dot for active/running status.

### Form Inputs (`<Input>`, `<Select>`, `<Slider>`)
- Dark inset backgrounds `rgba(15, 23, 42, 0.7)`.
- Focused state: 2px ring with `var(--accent-primary)`.
- Custom styled native select and range sliders with live readout labels.

---

## 6. Layout & 5-Step Sequential Workflow
1. **Step 1: Art Direction** (Split grid: Moodboard upload / Direct upload on left; Master Prompt review + 9-category levers + 4-baseline selector on right).
2. **Step 2: Refinement** (Left: Multi-turn prompt conversation & seed locking; Right: Master viewport with split-slider before/after).
3. **Step 3: Canvas / Inpaint** (Left: Dual-layer brush/mask tools, prompt guidance; Right: Master viewport before/after inpaint).
4. **Step 4: Wardrobe** (Left: Garment wardrobe catalog & pinned layers; Right: Master viewport with interactive garment drop pins).
5. **Step 5: Export** (Dedicated aspect ratio grid, upscale engine, ZIP bundle download).
