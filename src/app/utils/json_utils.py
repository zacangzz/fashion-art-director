from typing import Any, Optional


def strip_empty_sections(value: Any, removed: Optional[list[dict[str, Any]]] = None, path: str = "") -> Any:
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
