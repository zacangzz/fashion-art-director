from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union

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

class PromptConflict(BaseModel):
    id: str = Field(description="Unique conflict identifier")
    severity: Literal["warning", "error", "info"] = "warning"
    conflicting_elements: List[str] = Field(default_factory=list, description="Contradicting phrases or tag labels")
    categories: List[str] = Field(default_factory=list, description="Categories containing conflicting elements")
    explanation: str = Field(description="Explanation of why these instructions fight for dominance")
    recommendation: Optional[str] = Field(default=None, description="Suggested resolution")


class BaselineSummary(BaseModel):
    id: str
    seed: int
    image_url: str
    created_at: str
    aspect_ratio: Optional[str] = None
    resolution: Optional[Dict[str, int]] = None
    compiled_prompt: Optional[str] = None
    temperature: Optional[float] = None


class AnalyzeAndBaselinesResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    moodboard_id: str
    master_prompt: Optional[str] = None
    narrative: str = ""
    categories: Dict[str, List[TagChip]] = Field(default_factory=dict)
    schema_data: Optional[Dict[str, Any]] = Field(alias="schema", default=None)
    baselines: List[BaselineSummary] = Field(default_factory=list)
    conflicts: List[PromptConflict] = Field(default_factory=list)


class DirectPhotoUploadResponse(BaseModel):
    generation_id: str
    image_url: str
    seed: int
    aspect_ratio: str
    resolution: Dict[str, int]
    compiled_prompt: str
    created_at: str


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
    aspect_ratio: Optional[str] = "1:1"
    negative_prompt: Optional[str] = None
    imagen_model: Optional[str] = None


class FineTuneGenerationResponse(BaseModel):
    generation_id: str
    parent_id: Optional[str] = None
    seed: int
    compiled_prompt: str
    negative_prompt: str
    image_url: str
    created_at: str
    aspect_ratio: Optional[str] = None
    resolution: Optional[Dict[str, int]] = None


class ExportBundleRequest(BaseModel):
    generation_id: str


class PrepareExportRequest(BaseModel):
    generation_id: str
    prompt_override: Optional[str] = None


class PrepareExportResponse(BaseModel):
    generation_id: str
    parent_id: Optional[str] = None
    seed: Optional[int] = None
    compiled_prompt: str
    negative_prompt: str = ""
    master_image_url: str
    aspect_ratio: Optional[str] = None
    resolution: Optional[Dict[str, int]] = None
    created_at: str


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
    aspect_ratio: str = "1:1"
    resolution_width: int = 3840
    resolution_height: int = 3840
    model_name: Optional[str] = None
    cost_usd: float = 0.0
    tokens: int = 0
    accumulated_cost_usd: float = 0.0
    accumulated_tokens: int = 0


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
    aspect_ratio: Optional[str] = None
    resolution: Optional[Dict[str, int]] = None
    cost_usd: Optional[float] = 0.0
    tokens: Optional[int] = 0
    accumulated_cost_usd: Optional[float] = 0.0
    accumulated_tokens: Optional[int] = 0


class HistoryResponse(BaseModel):
    generations: List[GenerationRecordResponse] = Field(default_factory=list)


class LineageResponse(BaseModel):
    root_id: str
    ancestors: List[GenerationRecordResponse] = Field(default_factory=list)
    descendants: List[GenerationRecordResponse] = Field(default_factory=list)


# ==============================================================================
# Conversation-Based Refinement Models
# ==============================================================================

class RefinementRequest(BaseModel):
    parent_id: str
    prompt: str
    seed_mode: str = "locked"
    seed: int = 4289102
    aspect_ratio: Optional[str] = "1:1"
    negative_prompt: Optional[str] = None
    conversation_id: Optional[str] = None
    imagen_model: Optional[str] = None


class RefinementResponse(BaseModel):
    generation_id: str
    parent_id: Optional[str] = None
    seed: int
    compiled_prompt: str
    negative_prompt: str
    image_url: str
    created_at: str
    aspect_ratio: Optional[str] = None
    resolution: Optional[Dict[str, int]] = None
    conversation_id: Optional[str] = None
    cost_usd: Optional[float] = 0.0
    tokens: Optional[int] = 0
    accumulated_cost_usd: Optional[float] = 0.0
    accumulated_tokens: Optional[int] = 0


class ConversationMessage(BaseModel):
    role: str  # "baseline" | "user"
    prompt: Optional[str] = None
    generation_id: str
    image_url: str
    seed: int
    created_at: str
    aspect_ratio: Optional[str] = None
    resolution: Optional[Dict[str, int]] = None


class ConversationResponse(BaseModel):
    conversation_id: str
    baseline_generation_id: str
    messages: List[ConversationMessage] = Field(default_factory=list)


# Legacy Request / Response Models
class MoodboardAnalysisSchema(BaseModel):
    model_config = ConfigDict(extra="allow")


class MoodboardAnalysisResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    moodboard_id: str
    master_prompt: Optional[str] = None
    narrative: str = ""
    categories: Dict[str, List[TagChip]] = Field(default_factory=dict)
    schema_data: Optional[Dict[str, Any]] = Field(alias="schema", default=None)
    extracted_chips: List[TagChip] = Field(default_factory=list)
    extracted_json: Optional[Dict[str, Any]] = None
    conflicts: List[PromptConflict] = Field(default_factory=list)


class GenerateBaselinesRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    moodboard_id: str
    master_prompt: Optional[str] = None
    narrative: Optional[str] = ""
    categories: Optional[Dict[str, List[Union[TagChip, Dict[str, Any]]]]] = None
    schema_data: Optional[Dict[str, Any]] = Field(alias="schema", default=None)
    aspect_ratio: Optional[str] = "1.8:1"
    prompt_override: Optional[str] = None
    imagen_model: Optional[str] = None
    temperature: Optional[float] = 1.0


class GenerateBaselinesResponse(BaseModel):
    moodboard_id: str
    baselines: List[BaselineSummary] = Field(default_factory=list)


class ResyncPromptFromLeversRequest(BaseModel):
    narrative: Optional[str] = ""
    categories: Optional[Dict[str, Any]] = None
    previous_master_prompt: Optional[str] = None
    vision_model: Optional[str] = None


class ResyncPromptFromLeversResponse(BaseModel):
    master_prompt: str
    narrative: str
    conflicts: List[PromptConflict] = Field(default_factory=list)


class ResyncLeversFromPromptRequest(BaseModel):
    master_prompt: str
    narrative: Optional[str] = ""
    categories: Optional[Dict[str, Any]] = None
    vision_model: Optional[str] = None


class ResyncLeversFromPromptResponse(BaseModel):
    categories: Dict[str, List[TagChip]] = Field(default_factory=dict)
    narrative: str
    conflicts: List[PromptConflict] = Field(default_factory=list)


class ResyncMasterPromptRequest(BaseModel):
    narrative: Optional[str] = ""
    categories: Optional[Dict[str, Any]] = None
    previous_master_prompt: Optional[str] = None
    master_prompt: Optional[str] = None
    vision_model: Optional[str] = None


class ResyncMasterPromptResponse(BaseModel):
    master_prompt: str = ""
    narrative: str = ""
    categories: Dict[str, List[TagChip]] = Field(default_factory=dict)
    conflicts: List[PromptConflict] = Field(default_factory=list)


class CheckConflictsRequest(BaseModel):
    master_prompt: Optional[str] = ""
    narrative: Optional[str] = ""
    categories: Optional[Dict[str, Any]] = None
    vision_model: Optional[str] = None


class CheckConflictsResponse(BaseModel):
    conflicts: List[PromptConflict] = Field(default_factory=list)


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
    imagen_model: Optional[str] = None


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
    cost_usd: Optional[float] = 0.0
    tokens: Optional[int] = 0
    accumulated_cost_usd: Optional[float] = 0.0
    accumulated_tokens: Optional[int] = 0


# ==============================================================================
# Wardrobe Composition Models
# ==============================================================================

class DetectedGarment(BaseModel):
    label: str = Field(description="Descriptive title of the garment, footwear, or accessory")
    category: Literal["outerwear", "tops", "bottoms", "footwear", "accessories", "full_outfit"] = Field(
        default="tops", description="Garment classification"
    )
    box_2d: List[int] = Field(
        description="Bounding box [ymin, xmin, ymax, xmax] as integers on a 0 to 1000 scale"
    )


class WardrobeSegmentationResult(BaseModel):
    items: List[DetectedGarment] = Field(
        default_factory=list,
        description="List of detected standalone garments, footwear, and accessories"
    )


class ClothingRegionItem(BaseModel):
    label: str = Field(description="Descriptive label of the subject clothing region")
    category: Literal["outerwear", "tops", "bottoms", "footwear", "accessories", "full_outfit"] = Field(
        default="tops", description="Region classification"
    )
    box_2d: List[int] = Field(
        description="Bounding box [ymin, xmin, ymax, xmax] as integers on a 0 to 1000 scale"
    )


class ClothingRegionDetectionResult(BaseModel):
    regions: List[ClothingRegionItem] = Field(
        default_factory=list,
        description="List of detected subject clothing regions"
    )


class GarmentExtractedDetails(BaseModel):
    garment_type: Optional[str] = Field(default=None, description="Specific clothing type (e.g. T-Shirt, Hoodie, Jeans)")
    primary_color: Optional[str] = Field(default=None, description="Dominant primary color hue")
    secondary_colors: List[str] = Field(default_factory=list, description="Secondary accent colors or trim colors")
    fabric_texture: Optional[str] = Field(default=None, description="Material weave, weight, and fabric texture")
    has_graphic_or_print: bool = Field(default=False, description="Whether the garment features graphic artwork, illustrations, or patterns")
    has_text_or_logo: bool = Field(default=False, description="Whether visible text, slogans, or logos appear on the garment")
    exact_text_content: List[str] = Field(default_factory=list, description="Exact transcription of all letters, numbers, and slogans visible on the garment")
    graphic_description: Optional[str] = Field(default=None, description="Detailed description of graphic art, symbols, illustrations, or distressed print effects")
    logo_and_print_placement: Optional[str] = Field(default=None, description="Anatomical placement (e.g. Center chest, Left breast pocket, Full back)")
    hardware_and_details: Optional[str] = Field(default=None, description="Hardware details such as buttons, zippers, drawstrings, distress, stitching")


class GarmentCard(BaseModel):
    id: str
    label: str
    category: Optional[str] = "tops"
    image_url: str
    upscaled_image_url: Optional[str] = None
    source_image_url: Optional[str] = None
    bbox: Optional[List[float]] = None
    extracted_details: Optional[Union[GarmentExtractedDetails, Dict[str, Any]]] = None
    created_at: Optional[str] = None
    upscale_status: Optional[str] = "pending"
    is_upscaled: bool = False
    cost_usd: float = 0.0
    tokens: int = 0


class WardrobeUploadResponse(BaseModel):
    items: List[GarmentCard] = Field(default_factory=list)


class WardrobeListResponse(BaseModel):
    items: List[GarmentCard] = Field(default_factory=list)


class ClothingRegion(BaseModel):
    id: str
    label: str
    category: Optional[str] = None
    bbox: List[float] = Field(default_factory=list)


class DetectRegionsRequest(BaseModel):
    generation_id: Optional[str] = None
    vision_model: Optional[str] = None


class DetectRegionsResponse(BaseModel):
    regions: List[ClothingRegion] = Field(default_factory=list)


class CompositionPinAssignment(BaseModel):
    wardrobe_item_id: str
    pin_number: int
    drop_position: Optional[Dict[str, float]] = None
    target_description: Optional[str] = None
    region_bbox: Optional[List[float]] = None
    grounded_subject: Optional[str] = None
    item_label: Optional[str] = None
    category: Optional[str] = None


class WardrobeComposeRequest(BaseModel):
    parent_id: str
    assignments: List[CompositionPinAssignment] = Field(default_factory=list)
    seed_mode: str = "locked"
    seed: int = 4289102
    aspect_ratio: Optional[str] = None
    negative_prompt: Optional[str] = None
    conversation_id: Optional[str] = None
    custom_instruction: Optional[str] = None
    imagen_model: Optional[str] = None
    vision_model: Optional[str] = None


class WardrobeComposeResponse(BaseModel):
    generation_id: str
    parent_id: Optional[str] = None
    seed: int
    compiled_prompt: str
    negative_prompt: str
    image_url: str
    created_at: str
    aspect_ratio: Optional[str] = "2:3"
    resolution: Optional[Dict[str, int]] = None
    conversation_id: Optional[str] = None
    assignments: List[CompositionPinAssignment] = Field(default_factory=list)
    cost_usd: Optional[float] = 0.0
    tokens: Optional[int] = 0
    accumulated_cost_usd: Optional[float] = 0.0
    accumulated_tokens: Optional[int] = 0

