
# Instructions for Agents to follow
* always use uv to manage python packages, DO NOT use pip.
* update pyproject.toml accordingly when new packages are required, or when packages are no longer required.
* work within the existing .venv, do not create new virtual environments.

## LESSONS.md
* when something new about API is learnt or discovered throuought the iteration and development process, request permission from the user to allow update of the lessons learnt in LESSONS.md

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