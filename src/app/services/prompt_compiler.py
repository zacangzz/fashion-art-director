from typing import Any, Dict, List, Optional
from app.utils.prompt_loader import (
    DEFAULT_NEGATIVE_PROMPT,
    IMAGE_GENERATION_SUFFIX,
    INPAINT_SYSTEM_PROMPT,
    INPAINT_SUFFIX,
    REFINEMENT_SYSTEM_PROMPT,
    WARDROBE_COMPOSITION_SYSTEM_PROMPT,
    GARMENT_UPSCALE_SYSTEM_PROMPT,
)
from app.utils.image_utils import ASPECT_RATIO_RESOLUTIONS, normalize_interaction_aspect_ratio

CATEGORY_DISPLAY_NAMES = {
    "subject_details": "Subject & Character Details",
    "wardrobe_hair": "Wardrobe & Hairstyle",
    "objects_props": "Objects & Key Props",
    "environment": "Environment & Setting",
    "layout_framing": "Layout & Framing",
    "camera_optics": "Camera & Optics",
    "lighting": "Lighting & Atmosphere",
    "color_profile": "Color Profile & Palette",
    "mood_era": "Mood, Vibe & Era",
    "custom": "Custom Details",
}


class PromptCompiler:
    """
    Modular compiler for structured tag dictionaries, scene schemas, delta prompts,
    inpainting instructions, and wardrobe composition prompts.
    """

    @staticmethod
    def extract_labels(cats: Optional[Dict[str, Any]], cat_key: str) -> List[str]:
        if not cats or not isinstance(cats, dict):
            return []
        items = cats.get(cat_key, [])
        labels = []
        for item in items:
            if isinstance(item, str) and item.strip():
                labels.append(item.strip())
            elif isinstance(item, dict):
                if item.get("enabled", True) is False:
                    continue
                lbl = str(item.get("label", "")).strip()
                if lbl:
                    labels.append(lbl)
            elif hasattr(item, "label"):
                if getattr(item, "enabled", True) is False:
                    continue
                lbl = str(getattr(item, "label", "")).strip()
                if lbl:
                    labels.append(lbl)
        return labels

    @classmethod
    def get_modified_categories(
        cls,
        current_categories: Optional[Dict[str, Any]] = None,
        baseline_categories: Optional[Dict[str, Any]] = None,
        current_narrative: Optional[str] = None,
        baseline_narrative: Optional[str] = None,
    ) -> Dict[str, Any]:
        curr = current_categories or {}
        base = baseline_categories or {}
        modified = {}
        all_keys = set(curr.keys()).union(set(base.keys()))
        for key in all_keys:
            curr_labels = cls.extract_labels(curr, key)
            base_labels = cls.extract_labels(base, key)
            if curr_labels != base_labels:
                modified[key] = True

        curr_narrative_clean = (current_narrative or "").strip()
        base_narrative_clean = (baseline_narrative or "").strip()
        narrative_modified = curr_narrative_clean != base_narrative_clean

        return {
            "categories": modified,
            "narrative": narrative_modified,
            "has_changes": narrative_modified or bool(modified),
        }

    @classmethod
    def compile_prompt(
        cls,
        narrative: Optional[str] = None,
        categories: Optional[Dict[str, Any]] = None,
        custom_tags: Optional[List[str]] = None,
        prompt_override: Optional[str] = None,
        master_prompt: Optional[str] = None,
    ) -> str:
        """
        Compiles a reproducible, structured modular narrative prompt from 9-category tags.
        """
        if prompt_override and prompt_override.strip():
            return prompt_override.strip()
        if master_prompt and master_prompt.strip():
            return master_prompt.strip()

        sections = []
        if narrative and narrative.strip():
            sections.append(narrative.strip())

        cats = categories or {}

        subject_labels = cls.extract_labels(cats, "subject_details")
        wardrobe_labels = cls.extract_labels(cats, "wardrobe_hair")
        object_labels = cls.extract_labels(cats, "objects_props")
        env_labels = cls.extract_labels(cats, "environment")
        framing_labels = cls.extract_labels(cats, "layout_framing")
        camera_labels = cls.extract_labels(cats, "camera_optics")
        lighting_labels = cls.extract_labels(cats, "lighting")
        color_labels = cls.extract_labels(cats, "color_profile")
        mood_labels = cls.extract_labels(cats, "mood_era")
        custom_labels = [c.strip() for c in (custom_tags or []) if c and c.strip()]
        custom_cat_labels = cls.extract_labels(cats, "custom")
        all_custom = custom_labels + custom_cat_labels

        if subject_labels or wardrobe_labels:
            parts = []
            if subject_labels:
                parts.append(", ".join(subject_labels))
            if wardrobe_labels:
                parts.append(f"wearing {', '.join(wardrobe_labels)}")
            sections.append(f"Subject: {', '.join(parts)}.")

        if env_labels or object_labels:
            parts = []
            if env_labels:
                parts.append(f"set in {', '.join(env_labels)}")
            if object_labels:
                parts.append(f"featuring {', '.join(object_labels)}")
            sections.append(f"Environment: {', '.join(parts)}.")

        if framing_labels or camera_labels:
            parts = []
            if framing_labels:
                parts.append(", ".join(framing_labels))
            if camera_labels:
                parts.append(f"shot on {', '.join(camera_labels)}")
            sections.append(f"Composition: {', '.join(parts)}.")

        if lighting_labels or color_labels:
            parts = []
            if lighting_labels:
                parts.append(f"illuminated with {', '.join(lighting_labels)}")
            if color_labels:
                parts.append(f"color palette of {', '.join(color_labels)}")
            sections.append(f"Lighting & Color: {', '.join(parts)}.")

        if mood_labels:
            sections.append(f"Aesthetic: {', '.join(mood_labels)}.")

        if all_custom:
            sections.append(f"Details: {', '.join(all_custom)}.")

        compiled = " ".join(sections).strip()
        return compiled or (narrative.strip() if narrative else "A high-fashion cinematic scene with exquisite detail.")

    @classmethod
    def compile_delta_prompt(
        cls,
        narrative: Optional[str] = None,
        categories: Optional[Dict[str, Any]] = None,
        baseline_narrative: Optional[str] = None,
        baseline_categories: Optional[Dict[str, Any]] = None,
        locked_categories: Optional[List[str]] = None,
        custom_tags: Optional[List[str]] = None,
        prompt_override: Optional[str] = None,
    ) -> str:
        """
        Compiles an Image-to-Image Delta Prompt when fine-tuning from a baseline image reference.
        """
        if prompt_override and prompt_override.strip():
            return prompt_override.strip()

        if not baseline_categories or not isinstance(baseline_categories, dict):
            return cls.compile_prompt(
                narrative=narrative,
                categories=categories,
                custom_tags=custom_tags,
                prompt_override=prompt_override,
            )

        cats = categories or {}
        diff = cls.get_modified_categories(
            current_categories=cats,
            baseline_categories=baseline_categories,
            current_narrative=narrative,
            baseline_narrative=baseline_narrative,
        )

        if not diff["has_changes"]:
            return (
                "Visual Continuity: Faithfully preserve the character identity, pose, framing, and environment "
                "from the input reference image while subtly refining overall render fidelity and atmospheric coherence."
            )

        sections = [
            "Visual Reference Foundation: Use the reference image as the structural, character, and stylistic anchor. "
            "Maintain raw photo fidelity, 1:1 original source sharpness, visible skin pores, natural skin texture, "
            "realistic teeth texture, natural tooth alignment, authentic gum line, subtle dental translucency, "
            "minor skin blemishes, natural light, and natural micro-contrast. "
            "Apply the requested modifications below seamlessly, allowing all naturally interconnected visual elements—including lighting falloff, cast shadows, material reactions, and environmental reflections—to adjust organically for realistic visual cohesion without waxy smoothing, artificial plastic finish, or compression degradation. "
            "Color Constancy & Calibrated White Balance Lock: Strictly preserve the exact Kelvin color temperature, neutral white balance, background chromaticity, neutral gray tones, and authentic skin undertones of the reference base image without introducing warm color casts, magenta/reddish tinting, or progressive warming filters."
        ]

        adjustments = []
        if diff["narrative"] and narrative and narrative.strip():
            adjustments.append(f"Scene Direction: {narrative.strip()}")

        category_diff_map = {
            "subject_details": ("Subject Details", "subject_details", ""),
            "wardrobe_hair": ("Wardrobe & Hairstyle", "wardrobe_hair", "wearing "),
            "objects_props": ("Objects & Props", "objects_props", "featuring "),
            "environment": ("Environment", "environment", "set in "),
            "layout_framing": ("Framing & Layout", "layout_framing", ""),
            "lighting": ("Lighting", "lighting", "illuminated with "),
            "color_profile": ("Color Profile", "color_profile", "palette of "),
            "camera_optics": ("Camera & Optics", "camera_optics", "shot on "),
            "mood_era": ("Aesthetic & Mood", "mood_era", ""),
            "custom": ("Custom Details", "custom", ""),
        }

        for cat_key, (header, key, prefix) in category_diff_map.items():
            if diff["categories"].get(key):
                lbls = cls.extract_labels(cats, key)
                if lbls:
                    adjustments.append(f"{header}: {prefix}{', '.join(lbls)}")

        if adjustments:
            sections.append(f"Requested Modifications: {'. '.join(adjustments)}.")

        all_known_categories = [
            "subject_details",
            "wardrobe_hair",
            "objects_props",
            "environment",
            "layout_framing",
            "camera_optics",
            "lighting",
            "color_profile",
            "mood_era",
        ]
        locked_set = set(locked_categories or [])
        preserved_categories = [
            CATEGORY_DISPLAY_NAMES.get(k, k)
            for k in all_known_categories
            if k in locked_set
        ]

        if preserved_categories:
            sections.append(
                f"Consistent Anchors: Maintain the core design, identity, and styling of {', '.join(preserved_categories)}, while allowing them to interact realistically with the updated scene conditions."
            )

        return "\n\n".join(sections).strip()

    @classmethod
    def format_inpaint_prompt(
        cls,
        prompt: str,
        mask_stats: Dict[str, Any],
        aspect_ratio: str,
        negative_prompt: Optional[str] = None,
    ) -> str:
        """
        Formats spatial inpainting prompt with bounding box context, aspect ratio, and system instructions.
        """
        res_tuple = ASPECT_RATIO_RESOLUTIONS.get(aspect_ratio or "2:3", (2560, 3840))
        res_str = f"{res_tuple[0]}x{res_tuple[1]}"
        norm_aspect = normalize_interaction_aspect_ratio(aspect_ratio)

        bbox_desc = "unspecified"
        centroid_desc = "unspecified"
        if mask_stats.get("bounding_box"):
            bb = mask_stats["bounding_box"]
            nb = mask_stats.get("normalized_bounding_box", {})
            bbox_desc = f"x=[{bb['min_x']}..{bb['max_x']}] (norm: {nb.get('min_x')}..{nb.get('max_x')}), y=[{bb['min_y']}..{bb['max_y']}] (norm: {nb.get('min_y')}..{nb.get('max_y')})"
        if mask_stats.get("centroid"):
            ct = mask_stats["centroid"]
            centroid_desc = f"x={ct['x']} (norm: {ct.get('norm_x')}), y={ct['y']} (norm: {ct.get('norm_y')})"

        spatial_context = (
            f"SPATIAL INPAINT CONTEXT:\n"
            f"- Masked Coverage: {mask_stats.get('coverage_percentage', 0.0)}% of frame\n"
            f"- Mask Bounding Box: {bbox_desc}\n"
            f"- Mask Center Point: {centroid_desc}\n"
            f"- Desired Modification: {prompt.strip()}\n"
        )

        inpaint_suffix_text = INPAINT_SUFFIX.format(
            RESOLUTION=res_str,
            ASPECT_RATIO=norm_aspect,
            NEGATIVE_PROMPT=negative_prompt or DEFAULT_NEGATIVE_PROMPT,
        )

        return f"{INPAINT_SYSTEM_PROMPT}\n\n{spatial_context}\n\n{inpaint_suffix_text}"

    @classmethod
    def format_refinement_prompt(cls, prompt: str) -> str:
        clean_p = prompt.strip()
        if "{USER_PROMPT}" in REFINEMENT_SYSTEM_PROMPT:
            return REFINEMENT_SYSTEM_PROMPT.replace("{USER_PROMPT}", clean_p)
        return f"{REFINEMENT_SYSTEM_PROMPT}\n\nEDIT INSTRUCTION:\n<edit>\n{clean_p}\n</edit>"

    @classmethod
    def format_background_refinement_prompt(
        cls,
        prompt: str,
        perspective_mode: str = "auto_align",
        depth_of_field: str = "natural",
        lighting_mode: str = "harmonize_ambient",
        spatial_placement_instruction: Optional[str] = None,
        camera_directive: Optional[str] = None,
        lighting_directive: Optional[str] = None,
    ) -> str:
        perspective_instructions = {
            "auto_align": (
                "- Level horizon lines, match vanishing points, and align camera perspective so the subjects and environment share an authentic 3D spatial field."
            ),
            "preserve_bg": (
                "- Retain the background reference environment's original camera angle, horizon line, and architectural perspective geometry exactly as shown in Image 2."
            ),
            "low_angle": (
                "- Frame from a dramatic low-angle, upward-facing perspective to match an elevated, powerful hero subject stance."
            ),
            "high_angle": (
                "- Frame from an elevated high-angle perspective looking slightly downward into the scene with a higher horizon line."
            ),
            "eye_level": (
                "- Level the horizon line and frame from an authentic, cinematic eye-level vantage point."
            ),
        }

        dof_instructions = {
            "natural": (
                "- Render a natural photographic depth of field: sharp foreground subjects with realistic optical focus falloff into the background environment."
            ),
            "cinematic_bokeh": (
                "- Render with a cinematic wide aperture profile (f/1.4 - f/1.8): keep the foreground subjects crisp and tack-sharp while rendering the background in creamy, high-end optical bokeh."
            ),
            "crisp_architectural": (
                "- Render with deep depth of field (f/8 - f/11): maintain crisp, high-detail architectural clarity across both foreground subjects and background structures."
            ),
        }

        lighting_instructions = {
            "harmonize_ambient": (
                "- Cast realistic environmental ambient light spill and subtle rim highlights from the background environment onto the contours of the subjects.\n"
                "- Render natural contact shadows and directional occlusion at the subjects' contact points to ground them believably."
            ),
            "match_white_balance": (
                "- Strictly preserve calibrated neutral white balance and authentic natural skin undertones on the subjects, while harmonizing background chromaticity to sit cohesively within the scene."
            ),
            "dramatic_contrast": (
                "- Increase directional lighting contrast, shaping the subjects with prominent rim lighting and deep environmental shadows corresponding to the background scene."
            ),
        }

        persp_text = camera_directive or perspective_instructions.get(perspective_mode, perspective_instructions["auto_align"])
        dof_text = dof_instructions.get(depth_of_field, dof_instructions["natural"])
        light_text = lighting_directive or lighting_instructions.get(lighting_mode, lighting_instructions["harmonize_ambient"])
        spatial_text = spatial_placement_instruction or "- Position the subjects naturally inside the scene room geometry, seamlessly grounded with authentic contact shadows."

        from app.utils.prompt_loader import BACKGROUND_HARMONIZATION_TEMPLATE
        return BACKGROUND_HARMONIZATION_TEMPLATE.format(
            perspective_instruction=persp_text,
            spatial_placement_instruction=spatial_text,
            depth_of_field_instruction=dof_text,
            lighting_instruction=light_text,
            user_prompt=prompt.strip() or "Seamlessly synthesize the subjects inside the reference background environment.",
        )



# Global functional aliases for backward compatibility
extract_category_labels = PromptCompiler.extract_labels
get_modified_categories = PromptCompiler.get_modified_categories
compile_prompt = PromptCompiler.compile_prompt
compile_delta_prompt = PromptCompiler.compile_delta_prompt
