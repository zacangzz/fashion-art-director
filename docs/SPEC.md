# Technical Specification (SPEC)

## Sparse Scene Schema Contract

`docs/fine_grained_image_generation_schema.md` is the canonical schema reference. Scene data is an opaque JSON object throughout the API and database; the backend does not coerce it into a fixed typed template.

Every extracted scene includes:

```json
{
  "schema_version": "1.0",
  "metadata": { "purpose": "marketing" },
  "canvas": { "orientation": "portrait" },
  "creative_direction": { "genre": "product_photography" },
  "style": { "medium": "photographic" }
}
```

All other top-level sections and nested fields are optional. Model output must be a JSON object and omits `null`, empty strings, empty arrays, and empty objects. Legacy data using `intent`, `description`, `frame_position`, or `dominant_colors` remains readable as pass-through JSON.

## Processing Flow

1. The vision service loads the extraction prompt, schema guide, and sparse one-shot example from `src/app/prompts/`.
2. It validates that the model returned a JSON object, preserves locked sections, and returns the sparse schema unchanged.
3. Generation recursively removes empty values, serializes the remaining JSON directly for the image model, and appends aspect ratio, seed, and negative-prompt instructions.
4. The same cleaned schema is stored with generation history.

`src/app/prompts/defaults.json` defines the default negative prompt. Prompt assets load at process start; restart the server after editing them.

## API Contract

- `POST /api/moodboard/analyze-and-generate` returns a sparse `schema` object with baseline images.
- `POST /api/generation/fine-tune` accepts the sparse `schema` object directly.
- `POST /api/generate` retains legacy input compatibility by serializing its supplied JSON or enabled chips locally.

There is no prompt-preview endpoint.

## Frontend Contract

The graph derives cards from top-level object and array values. `schema_version` and `metadata` stay on the root card. `canvas`, `creative_direction`, and `style` are required graph sections; optional object-valued sections can be added or deleted. The recursive `JsonTreeNode` powers nested object and array edits in the inspector, including read-only locked sections.
