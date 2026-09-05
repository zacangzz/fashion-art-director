# Gallery Lumina — Design System (`DESIGN.md`)

## 1. Brand Essence & Visual Language
**Gallery Lumina** embodies an immaculate, gallery-grade editorial light aesthetic tailored for premier fashion houses, creative directors, photographers, and luxury cultural institutions. The interface functions as an enlightened architectural pavilion: structural chrome recedes completely, offering an expansive, luminous white-cube stage where photography, textile texture, and visual curation command total prominence.

### Design Movement: Gallery-Grade Minimalist Editorial with Luminous Sky Accents
Merging Scandinavian exhibition architecture, limited-edition art monographs, and Swiss rationalist typographic precision, this aesthetic eliminates visual dust and grays in favor of crisp, pure radiance.

1. **Crisp Alabaster & Optic Whites**: Pure optic white cards and soft alabaster surfaces establish maximum luminosity and pristine chromatic fidelity for visual works.
2. **Architectural Discipline**: Layouts align to hair-thin structural grids and generous negative space, cultivating restraint, quiet luxury, and deliberate pacing.
3. **Luminous Sky Blue Accent**: A clean, fresh, radiant sky blue (`#2563EB`) brings crisp clarity, energy, and purity to key focal cues, status markers, and interactive states without muddying the canvas.
4. **Editorial High-Contrast Typography**: High-contrast Didone serifs (`Bodoni Moda`) anchor collection titles with timeless luxury, balanced by clinical grotesque sans-serifs (`Hanken Grotesk`) and monospaced technical notation (`JetBrains Mono`).
5. **Monograph Split Layout**: 5-column technical/curation panel on the left, 7-column luminous artwork stage on the right, keeping full focus and clarity on the hero image.

---

## 2. Color Palette & Design Tokens

### Surface & Neutral Tones
- **`--bg-canvas` / `--bg-dark`**: `#F9F9FB` (Gallery Chalk — Base page canvas)
- **`--bg-surface`**: `#FFFFFF` (Pure Optic White — Artwork mounts, cards, inspect panels)
- **`--bg-surface-elevated`**: `#F4F4F6` (Subtle Card Inset — Nested trays, toolbar docks)
- **`--bg-surface-hover`**: `#EBF3FE` (Sky Tint Light — Interactive hover wash)
- **`--bg-surface-active`**: `#DBEAFE` (Sky Tint Soft — Selected rows, active tabs)
- **`--border-color`**: `#EEEEF2` (Whisper Hairline — Static structural separations)
- **`--border-color-hover`**: `#E2E4E9` (Interactive Hairline — Outlines, form boundaries)
- **`--border-focus`**: `#2563EB` (Pure Sky Blue — Active focus rings and highlighted cards)

### Editorial Typography Scale
- **`--text-primary`**: `#18181B` (Deep Graphite — Authoritative headlines, primary labels)
- **`--text-secondary`**: `#71717A` (Editorial Neutral — Supportive body copy, subtitles)
- **`--text-muted`**: `#9CA3AF` (Muted Stone — Inactive icons, placeholders, technical indices)
- **`--text-inverse`**: `#FFFFFF` (Optic White — Text over solid graphite and sky blue buttons)

### Chromatic Accent Tokens (Luminous Sky Blue)
- **`--color-primary` / `--sky-blue-clean`**: `#2563EB` (The core vibrant cerulean accent)
- **`--color-primary-hover` / `--sky-blue-deep`**: `#1D4ED8` (High-contrast hover and active states)
- **`--color-accent-vibrant` / `--sky-blue-vibrant`**: `#3B82F6` (Hover outlines, illuminated focus)
- **`--sky-tint-light`**: `#EBF3FE` (Clean pastel blue wash for active backdrops)
- **`--sky-tint-soft`**: `#DBEAFE` (Subtle boundary rings and capsule tag fills)
- **`--sky-glow`**: `rgba(37, 99, 235, 0.16)` (Ambient focus halos and vitrine glints)

### Semantic Functional Status Tints
- **Success / Direct Ready**: `#10B981` (Emerald), soft fill: `rgba(16, 185, 129, 0.1)`
- **Warning / Seed Mode**: `#F59E0B` (Warm Amber), soft fill: `rgba(245, 158, 11, 0.1)`
- **Conflict / Danger**: `#BA1A1A` / `#EF4444` (Crimson Rose), soft fill: `rgba(239, 68, 68, 0.1)`

---

## 3. Typography Scale

- **Display & Collection Serifs (`font-serif`)**: `'Bodoni Moda', Georgia, 'Times New Roman', serif`
- **Grotesque UI & Body (`font-sans`)**: `'Hanken Grotesk', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif`
- **Technical Indexing & Monospace (`font-mono`)**: `'JetBrains Mono', 'Fira Code', monospace`

| Token / Role | Size | Line Height | Weight | Tracking | Usage |
|---|---|---|---|---|---|
| **`display-hero`** | `2.5rem` (40px) | `1.15` | 400 Regular (Serif) | `-0.02em` | Main Viewport Banners, Gallery Splash |
| **`headline-lg`** | `1.75rem` (28px) | `1.2` | 500 Medium (Serif) | `-0.01em` | Major Stage Headers, Section Titles |
| **`headline-md`** | `1.25rem` (20px) | `1.3` | 400 Regular (Serif) | `-0.01em` | Modal titles, Card Group Headers |
| **`headline-sm`** | `1.05rem` (17px) | `1.4` | 600 SemiBold (Sans) | `0.01em` | Card titles, Inspector Headers |
| **`body-lg`** | `1.0rem` (16px) | `1.6` | 400 Regular (Sans) | `0` | Editorial narrative, long descriptions |
| **`body-md`** | `0.875rem` (14px) | `1.5` | 400 Regular (Sans) | `0` | UI copy, chat prompts, lever values |
| **`body-sm`** | `0.75rem` (12px) | `1.4` | 400 Regular (Sans) | `0.01em` | Secondary metadata, helper labels |
| **`label-caps`** | `0.6875rem` (11px)| `1.3` | 600 SemiBold (Sans) | `0.14em` | Category eyebrows, button caps, headers |
| **`label-mono`** | `0.6875rem` (11px)| `1.3` | 500 Medium (Mono) | `0.04em` | Seeds, aspect ratios, model codes |
| **`caption-micro`**| `0.5625rem` (9px) | `1.2` | 500 Medium (Mono) | `0.08em` | Micro badges, status indicators |

---

## 4. Elevation, Radii & Depth

### Shape Language (Sharp Architectural Precision)
- **Sharp Monograph Geometry (`0px`)**: Cards, image frame mounts, buttons, dialogs, dropdowns, inputs, and tabs strictly enforce `border-radius: 0px`. This geometry echoes trimmed exhibition monographs and architectural gallery plinths.
- **Micro-Pills (`9999px`)**: Functional indicators (live availability status dots, artwork inspect pins, and curation filter capsules) use `border-radius: 9999px` to provide clear functional contrast against the surrounding rectilinear architecture.

### Vitrine Glass & Spatial Layering
- **Vitrine Glass**: Sticky navigation headers and floating toolbars use an airy glass treatment:
  ```css
  background: rgba(255, 255, 255, 0.88);
  backdrop-filter: blur(20px) saturate(160%);
  border-bottom: 1px solid rgba(238, 238, 242, 0.8);
  ```
- **Whisper Ambient Shadow**:
  ```css
  box-shadow: 0 24px 48px -12px rgba(24, 24, 27, 0.04), 0 4px 12px -2px rgba(24, 24, 27, 0.02);
  ```
- **Sky Blue Active Halos**:
  ```css
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.16);
  ```

---

## 5. UI Component Primitives Specs

### Buttons (`<Button>`)
- **Primary**: Solid deep graphite `#18181B` with pure white `#FFFFFF` text, `0px` radius, uppercase `label-caps` styling (`padding: 12px 24px`). On hover, surface shifts to `#27272A` with a crisp `2px` bottom accent in `#2563EB`.
- **Accent (Clean Sky Blue)**: Solid pure sky blue `#2563EB` with white `#FFFFFF` text, `0px` radius. Hover: `#1D4ED8`. Used selectively for key curation actions, direct generation, and export.
- **Secondary**: Optic white background (`#FFFFFF`), `1px solid #E2E4E9`, text in `#18181B`. On hover: background `#EBF3FE`, border shifts to `#3B82F6`, text shifts to `#2563EB`.
- **Ghost**: Transparent background, text `#71717A`. On hover: `#18181B` text with an ultra-thin hairline underline in `#2563EB`.
- **Danger**: Archival soft crimson wash (`#FEF2F2`), `1px solid #FECACA`, text `#DC2626`. On hover: `#DC2626` text with `#B91C1C` border.

### Badges & Curation Capsules (`<Badge>`)
- **Curation Capsule**: `border-radius: 9999px`, `1px solid #DBEAFE`, background `#EBF3FE`, typography in `caption-micro` (`#2563EB`). Houses a 5px status pip in `#2563EB`.
- **Status Pills**: Muted stone or status color dot (Emerald for ready, Amber for processing, Rose for error) housed within a soft pill capsule.

### Cards & Workspaces (`<Card>`)
- Pure white `#FFFFFF` surface, `0px` radius, encased in `1px solid #EEEEF2`.
- Active / Selected Card State: border sharpens to `1px solid #2563EB` with ambient halo.

### Form Fields & Inputs (`<Input>`, `<Select>`, `<Slider>`)
- **Text Inputs & Textareas**: Optic white `#FFFFFF`, `1px solid #E2E4E9`, text `#18181B`, placeholder `#9CA3AF`, `0px` radius. On focus: `1px solid #2563EB` with ambient halo (`box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.16)`).
- **Range Sliders**: 1px hairline track in `#EEEEF2` with completed track filled in `#2563EB`. Scrubber is a crisp 10px square `#18181B` handle with an inner 2px dot in `#2563EB`.

### Modals (`<Modal>`)
- Pure white container, `0px` radius, `1px solid #E2E4E9`, cast with whisper ambient shadow.
- Backdrop: Archival frosted glass (`background: rgba(24, 24, 27, 0.25); backdrop-filter: blur(12px)`).
- Header: Bodoni Moda editorial title, subtle close icon button.

---

## 6. Monograph Split Layout & 5-Step Workflow
The application layout centers on the **Monograph Split** architecture:
- **Left Column (5 cols / ~38%)**: Technical & curatorial controls, prompt conversation, lever adjustments, inpaint tools, or wardrobe catalog.
- **Right Column (7 cols / ~62%)**: Expansive archival image canvas viewport (`CanvasViewport`), featuring edge-to-edge mounting, floating minimal pills for zoom/comparison, and clinical diagnostic readouts.

### Workflow Stages
1. **Stage 01: Art Direction** (Left: Reference moodboard upload / Direct upload; Right: Master Prompt synthesis, 9 visual levers, 4-baseline exhibition grid).
2. **Stage 02: Adjust** (Toolbar submodes: `Refinement` prompt conversation & `Adjust` precision canvas brush inpaint; Right: Master picture mount with before/after split slider).
3. **Stage 03: Scene** (Toolbar submodes: `Wardrobe` garment catalog & `Props` object staging; Right: Interactive spatial pins/boxes on canvas).
4. **Stage 04: Master Export** (Left: Aspect ratio selector & resolution parameters; Right: Exhibition preview & high-resolution bundle download).
