import json
from typing import Any, Optional


def clean_json_text(text: str) -> str:
    """
    Strips markdown code fences (```json ... ```) and leading/trailing whitespace
    from raw LLM response text.
    """
    if not text:
        return ""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    return cleaned


def parse_json_safely(text: str, default: Any = None) -> Any:
    """
    Cleans markdown formatting and parses JSON string safely, returning `default` on error.
    """
    if not text or not isinstance(text, str):
        return default
    cleaned = clean_json_text(text)
    try:
        return json.loads(cleaned)
    except Exception:
        return default


def strip_empty_sections(
    value: Any,
    removed: Optional[list[dict[str, Any]]] = None,
    path: str = "",
) -> Any:
    """
    Recursively strips None, empty strings, empty lists, and empty dicts from nested structures.
    """
    if isinstance(value, dict):
        cleaned = {}
        for key, item in value.items():
            item_path = f"{path}/{key}"
            if item in (None, "", [], {}):
                if removed is not None:
                    removed.append({"path": item_path, "value": item})
                continue
            cleaned_item = strip_empty_sections(item, removed, item_path)
            if cleaned_item in (None, "", [], {}):
                if removed is not None:
                    removed.append({"path": item_path, "value": cleaned_item})
                continue
            cleaned[key] = cleaned_item
        return cleaned
    if isinstance(value, list):
        cleaned = []
        for index, item in enumerate(value):
            item_path = f"{path}/{index}"
            if item in (None, "", [], {}):
                if removed is not None:
                    removed.append({"path": item_path, "value": item})
                continue
            cleaned_item = strip_empty_sections(item, removed, item_path)
            if cleaned_item in (None, "", [], {}):
                if removed is not None:
                    removed.append({"path": item_path, "value": cleaned_item})
                continue
            cleaned.append(cleaned_item)
        return cleaned
    return value
