
# Instructions for Agents to follow
* always use uv to manage python packages, DO NOT use pip.
* update pyproject.toml accordingly when new packages are required, or when packages are no longer required.
* work within the existing .venv, do not create new virtual environments.
* always ensure that code is written in a way that is easy to understand and maintain.
    * apply OOP principles, especially using Composition over Inheritance.
    * do not overly engineer code or create exessive redundancies when simple modular methods work.
* avoid using in-line prompts, always create prompt templates in a separate file and import them.

## LESSONS.md
* when something new about API is learnt or discovered throuought the iteration and development process, request permission from the user to allow update of the lessons learnt in LESSONS.md
* in writing lessons learnt: be concise, keep it short and sweet, cover the main points and where necessary include appropriate code snippets or commands for clarity

## Gemini Interactions API (`client.interactions.create`) Guidelines

### 1. Structured JSON Output (`response_format`)
* **NEVER** use `{"type": "json"}` in `response_format`. The value `'json'` is **NOT** a supported type and will throw a `400 Bad Request` (`The value 'json' is not supported for 'type' at 'response_format'`).
* Supported values for `type` in `response_format` are: `'audio'`, `'text'`, `'number'`, `'integer'`, `'object'`, `'image'`, `'array'`, `'video'`, `'string'`, `'boolean'`.
* To request JSON / Structured Output from Gemini models, always configure `type: "text"` with `mime_type: "application/json"`:

```python
# PROPER PATTERN: JSON / Structured Text Output
interaction = client.interactions.create(
    model="gemini-3.7-flash", # or gemini-3.5-flash-lite
    input=user_prompt,
    system_instruction=system_prompt,
    response_format={
        "type": "text",
        "mime_type": "application/json",
        # Optional Pydantic/JSON schema:
        # "schema": MyModel.model_json_schema()
    },
    generation_config={
        "temperature": 0.4,
    }
)
output_json_str = interaction.output_text
```

### 2. Image Generation Output (`response_format`)
```python
# PROPER PATTERN: Image Output (Nano Banana / Imagen)
interaction = client.interactions.create(
    model="gemini-3.1-flash-image", # or gemini-3-pro-image, gemini-3.1-flash-lite-image
    input=input_items_or_prompt,
    response_format={
        "type": "image",
        "aspect_ratio": "16:9", # supported: 1:1, 16:9, 9:16, 4:3, 3:4, etc.
        "image_size": "4K",
    },
    generation_config={
        "temperature": 1.0,
    }
)
```

## Frontend Architecture & Design System Guidelines

When modifying existing pages or creating new views in `src/frontend/`:

1. **Design System & Aesthetics ([DESIGN.md](file:///Users/zacang/Documents/datascience/image-gen-pipeline/DESIGN.md))**:
   - Adhere strictly to the **Luxury Obsidian Dark** theme:
     - Base canvas: `--bg-dark` (`#07090e`), Panel surfaces: `--bg-surface` (`#10141e`), Elevated modals/popovers: `--bg-surface-elevated` (`#171d2b`).
     - Accents: Electric Indigo (`#6366f1` / `#a855f7`), Vision Cyan (`#06b6d4`), Success Emerald (`#10b981`), Warning Amber (`#f59e0b`), Conflict Rose (`#ef4444`).
     - Glassmorphism: Semi-transparent borders (`rgba(255, 255, 255, 0.08)`), multi-tier backdrop blurs (`backdrop-filter: blur(14px)`), and radial glow backdrops.
   - Typography: Use `Inter` for UI copy, buttons, and headings; use `JetBrains Mono` for technical metadata, resolutions, aspect ratios, and seeds.

2. **Atomic UI Primitives & Composition (`components/ui/`)**:
   - **Always compose shared UI primitives** ([`Button`](file:///Users/zacang/Documents/datascience/image-gen-pipeline/src/frontend/src/components/ui/Button.jsx), [`Modal`](file:///Users/zacang/Documents/datascience/image-gen-pipeline/src/frontend/src/components/ui/Modal.jsx), [`Badge`](file:///Users/zacang/Documents/datascience/image-gen-pipeline/src/frontend/src/components/ui/Badge.jsx), [`Card`](file:///Users/zacang/Documents/datascience/image-gen-pipeline/src/frontend/src/components/ui/Card.jsx), [`Select`](file:///Users/zacang/Documents/datascience/image-gen-pipeline/src/frontend/src/components/ui/Select.jsx), [`Input`](file:///Users/zacang/Documents/datascience/image-gen-pipeline/src/frontend/src/components/ui/Input.jsx), [`Slider`](file:///Users/zacang/Documents/datascience/image-gen-pipeline/src/frontend/src/components/ui/Slider.jsx)) from `src/frontend/src/components/ui/` instead of writing ad-hoc raw elements.
   - Avoid creating duplicate modal backdrops, button classes, or custom badges.
   - Apply **Composition over Inheritance** with clear, modular props.

3. **State Management & Custom Domain Hooks (`hooks/`)**:
   - Keep page and coordinator components (like [`App.jsx`](file:///Users/zacang/Documents/datascience/image-gen-pipeline/src/frontend/src/App.jsx)) lean (~150–250 lines).
   - Encapsulate domain workflows, API integrations, and transient state into custom React hooks in `src/frontend/src/hooks/` (e.g. `useMoodboardAnalysis`, `useRefinementStudio`, `useWardrobeComposer`, `useLineageHistory`).
   - Do NOT introduce heavy external state management libraries when simple modular hooks work.

4. **UX, Accessibility & Keyboard Ergonomics**:
   - Modals and drawers must support `Esc` key dismissal, backdrop click dismiss, and body scroll locking.
   - Support `Cmd/Ctrl + Enter` keyboard shortcuts for prompt submissions and refinement chats.
   - Ensure high typographic contrast and semantic ARIA labeling for all interactive controls.