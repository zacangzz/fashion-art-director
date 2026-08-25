from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


# ==============================================================================
# 9 Granular Tag Categories & Tag Models
# ==============================================================================

class TagCategory(str, Enum):
    SUBJECT_DETAILS = "subject_details"
    OBJECTS_PROPS = "objects_props"
    WARDROBE_HAIR = "wardrobe_hair"
    ENVIRONMENT = "environment"
    LAYOUT_FRAMING = "layout_framing"
    LIGHTING = "lighting"
    COLOR_PROFILE = "color_profile"
    CAMERA_OPTICS = "camera_optics"
    MOOD_ERA = "mood_era"
    CUSTOM = "custom"
    # Legacy aliases
    SUBJECT_OBJECTS = "subject_details"
    MEDIUM_CAMERA = "camera_optics"
    LIGHTING_ATMOSPHERE = "lighting"
    COLOR_PALETTE = "color_profile"
    COMPOSITION_FRAMING = "layout_framing"
    VIBE_STYLE = "mood_era"


TAG_CATEGORY_METADATA = {
    TagCategory.SUBJECT_DETAILS: {"label": "Subject & Character Details", "color": "#06b6d4"},
    TagCategory.OBJECTS_PROPS: {"label": "Objects & Key Props", "color": "#f97316"},
    TagCategory.WARDROBE_HAIR: {"label": "Wardrobe & Hairstyle", "color": "#ec4899"},
    TagCategory.ENVIRONMENT: {"label": "Environment & Setting", "color": "#84cc16"},
    TagCategory.LAYOUT_FRAMING: {"label": "Layout & Framing", "color": "#10b981"},
    TagCategory.LIGHTING: {"label": "Lighting & Atmosphere", "color": "#f59e0b"},
    TagCategory.COLOR_PROFILE: {"label": "Color Profile & Palette", "color": "#e11d48"},
    TagCategory.CAMERA_OPTICS: {"label": "Camera & Optical Specs", "color": "#a855f7"},
    TagCategory.MOOD_ERA: {"label": "Mood, Vibe & Era", "color": "#3b82f6"},
    TagCategory.CUSTOM: {"label": "Custom Tags", "color": "#64748b"},
}


class TagChip(BaseModel):
    id: str
    category: Union[TagCategory, str]
    label: str
    enabled: bool = True
    locked: bool = False
    weight: float = 1.0
    isCustom: bool = False


class TagStudioState(BaseModel):
    master_prompt: Optional[str] = None
    narrative: str = ""
    categories: Dict[str, List[TagChip]] = Field(default_factory=dict)
    locked_categories: List[str] = Field(default_factory=list)


# For backwards compatibility with any existing tests/code
class SceneSchema(BaseModel):
    model_config = ConfigDict(extra="allow")


# ==============================================================================
# API Contract Models
# ==============================================================================

class BaselineSummary(BaseModel):
    id: str
    seed: int
    image_url: str
    created_at: str
    aspect_ratio: Optional[str] = "2:3"
    resolution: Optional[Dict[str, int]] = None
    compiled_prompt: Optional[str] = None


class AnalyzeAndBaselinesResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    moodboard_id: str
    master_prompt: Optional[str] = None
    narrative: str = ""
    categories: Dict[str, List[TagChip]] = Field(default_factory=dict)
    schema_data: Optional[Dict[str, Any]] = Field(alias="schema", default=None)
    baselines: List[BaselineSummary] = Field(default_factory=list)


class FineTuneGenerationRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    parent_id: Optional[str] = None
    narrative: Optional[str] = None
    categories: Optional[Dict[str, List[Union[TagChip, Dict[str, Any]]]]] = None
    baseline_narrative: Optional[str] = None
    baseline_categories: Optional[Dict[str, Any]] = None
    locked_categories: Optional[List[str]] = None
    prompt_override: Optional[str] = None
    schema_data: Optional[Union[SceneSchema, Dict[str, Any]]] = Field(alias="schema", default=None)
    seed_mode: str = "locked"
    seed: int = 4289102
    use_image_reference: bool = True
    aspect_ratio: Optional[str] = "2:3"
    negative_prompt: Optional[str] = None


class FineTuneGenerationResponse(BaseModel):
    generation_id: str
    parent_id: Optional[str] = None
    seed: int
    compiled_prompt: str
    negative_prompt: str
    image_url: str
    created_at: str
    resolution: Optional[Dict[str, int]] = None


class ExportBundleRequest(BaseModel):
    generation_id: str


class GenerationRecordResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str
    parent_id: Optional[str] = None
    moodboard_id: Optional[str] = None
    is_baseline: bool = False
    created_at: str
    schema_dict: Dict[str, Any] = Field(alias="schema_json", default_factory=dict)
    compiled_prompt: str
    negative_prompt: str
    seed: int
    master_image_url: str
    mask_image_url: Optional[str] = None
    inpaint_metadata: Optional[Dict[str, Any]] = None
    aspect_ratio: str = "2:3"
    resolution_width: int = 1440
    resolution_height: int = 1440


class InpaintResponse(BaseModel):
    generation_id: str
    parent_id: Optional[str] = None
    seed: int
    compiled_prompt: str
    negative_prompt: str
    image_url: str
    mask_url: Optional[str] = None
    mask_stats: Optional[Dict[str, Any]] = None
    created_at: str
    resolution: Optional[Dict[str, int]] = None



class HistoryResponse(BaseModel):
    generations: List[GenerationRecordResponse] = Field(default_factory=list)


class LineageResponse(BaseModel):
    root_id: str
    ancestors: List[GenerationRecordResponse] = Field(default_factory=list)
    descendants: List[GenerationRecordResponse] = Field(default_factory=list)


# Legacy Request / Response Models
class MoodboardAnalysisSchema(BaseModel):
    model_config = ConfigDict(extra="allow")


class MoodboardAnalysisResponse(BaseModel):
    moodboard_id: str
    extracted_chips: List[TagChip] = Field(default_factory=list)
    extracted_json: Optional[Dict[str, Any]] = None


class GenerationRequest(BaseModel):
    moodboard_id: Optional[str] = None
    parent_generation_id: Optional[str] = None
    chips: Optional[List[TagChip]] = Field(default_factory=list)
    prompt_json: Optional[Dict[str, Any]] = None
    schema_data: Optional[Dict[str, Any]] = Field(alias="schema", default=None)
    seed_mode: str = "locked"
    seed: int = 4289102
    negative_prompt: str = ""
    aspect_ratio: str = "1:1"


class Resolution(BaseModel):
    width: int
    height: int


class GenerationResponse(BaseModel):
    generation_id: str
    created_at: str
    compiled_prompt: str
    seed: int
    master_image_url: str
    resolution: Resolution
