# Fine-Grained Image Generation JSON Schema

This document defines a **single canonical JSON template for generating an image as-is** with fine-grained control over composition, subjects, objects, surfaces, relationships, lighting, camera, color, style, typography, post-processing, and constraints.

The schema is designed around four principles:

1. **One canonical home per visual property** — avoid duplicated or conflicting instructions.
2. **Fine-grained when needed, sparse when not** — omit fields that do not matter.
3. **Machine-readable where possible** — use normalized values, IDs, coordinates, and structured relationships.
4. **Human-editable by design** — descriptive text is allowed where strict structure would be unnecessarily limiting.

---

## 1. Full JSON Template

```json
{
  "schema_version": "1.0",

  "metadata": {
    "scene_id": "scene_001",
    "name": "Retro Outdoor Furniture Editorial",
    "description": "A playful retro-inspired editorial furniture campaign set outdoors on a sunlit lawn.",
    "purpose": "marketing",
    "tags": ["editorial", "furniture", "retro", "outdoor", "lifestyle"]
  },

  "canvas": {
    "aspect_ratio": {"width": 2, "height": 3},
    "orientation": "portrait",
    "resolution": {"width_px": 1024, "height_px": 1536},
    "crop_policy": "preserve_primary_focal_points"
  },

  "creative_direction": {
    "genre": "editorial_commercial",
    "primary_mood": "playful",
    "secondary_moods": ["premium", "relaxed", "retro"],
    "realism": 0.90,
    "stylization": 0.30,
    "candidness": 0.80,
    "premium_feel": 0.75,
    "era_reference": "1970s"
  },

  "composition": {
    "layout": "multi_element",
    "balance": "asymmetric",
    "primary_focal_point": "subject_child_01",
    "secondary_focal_points": ["object_table_lamp_01"],
    "visual_flow": [
      "subject_child_01",
      "object_table_lamp_01",
      "object_red_floor_lamp_01",
      "object_backdrop_01"
    ],
    "depth_order": ["foreground", "midground", "background"],
    "negative_space": {
      "amount": 0.25,
      "preferred_regions": ["top_center"]
    }
  },

  "subjects": [
    {
      "id": "subject_child_01",
      "type": "person",
      "role": "primary",
      "importance": 1.0,
      "appearance": {
        "age_group": "young_child",
        "gender_presentation": null,
        "skin_tone": null,
        "hair": {
          "color": "copper_ginger",
          "length": "shoulder_length",
          "cut": "blunt_with_soft_layers",
          "texture": "mostly_straight_with_loose_natural_waves",
          "volume": "moderate",
          "part": "slightly_left_of_center",
          "styling": "natural_unstyled",
          "imperfections": ["flyaways", "wind_tousled_fringe", "uneven_distribution"]
        },
        "distinguishing_features": ["sunlit ginger flyaways forming a subtle golden halo"]
      },
      "wardrobe": {
        "outfit": [
          {
            "garment": "sweater",
            "color": null,
            "material": null,
            "fit": "relaxed"
          }
        ],
        "footwear": null,
        "accessories": []
      },
      "pose": {
        "posture": "seated",
        "body_rotation_deg": 45,
        "head_rotation_deg": 0,
        "head_tilt_deg": 0,
        "shoulders": "relaxed",
        "weight_distribution": "back_against_sofa",
        "gesture": "right_hand_raised_to_mouth"
      },
      "expression": {
        "emotion": "content",
        "mouth": "pursed",
        "eyes": "slightly_squinting",
        "eyebrows": "relaxed",
        "gaze_target": null,
        "expression_style": "candid"
      },
      "hands": {
        "left": {"visibility": "mostly_hidden", "action": "resting", "object_id": null},
        "right": {"visibility": "visible", "action": "holding", "object_id": "object_snack_01"}
      },
      "frame": {
        "center_x": 0.67,
        "center_y": 0.52,
        "width": 0.27,
        "height": 0.40,
        "rotation_deg": 0
      },
      "depth_plane": "midground"
    }
  ],

  "objects": [
    {
      "id": "object_sofa_01",
      "type": "sofa",
      "role": "hero_product",
      "importance": 0.95,
      "appearance": {
        "shape": "retro_outdoor_sofa",
        "style": "1970s_inspired",
        "condition": "pristine",
        "pattern": null
      },
      "materials": [
        {
          "component": "frame",
          "material": "painted_metal",
          "color": {"name": "terracotta", "hex": "#B84328"},
          "finish": "matte",
          "texture": "smooth"
        },
        {
          "component": "cushions",
          "material": "fabric",
          "color": {"name": "slate_blue_and_off_white", "hex": null},
          "finish": "matte",
          "texture": "woven"
        }
      ],
      "frame": {"center_x": 0.58, "center_y": 0.60, "width": 0.65, "height": 0.38, "rotation_deg": 0},
      "depth_plane": "midground",
      "state": {"visible": true, "quantity": 1}
    },
    {
      "id": "object_coffee_table_01",
      "type": "coffee_table",
      "role": "supporting_prop",
      "importance": 0.75,
      "appearance": {
        "shape": "low_rectangular",
        "style": "retro_modern",
        "condition": "pristine",
        "pattern": null
      },
      "materials": [
        {
          "component": "top",
          "material": "wood",
          "color": {"name": "natural_wood", "hex": null},
          "finish": "satin",
          "texture": "slatted"
        },
        {
          "component": "border",
          "material": "painted_metal",
          "color": {"name": "terracotta", "hex": "#B84328"},
          "finish": "matte",
          "texture": "smooth"
        }
      ],
      "frame": {"center_x": 0.28, "center_y": 0.78, "width": 0.40, "height": 0.24, "rotation_deg": 0},
      "depth_plane": "foreground",
      "state": {"visible": true, "quantity": 1}
    },
    {
      "id": "object_table_lamp_01",
      "type": "table_lamp",
      "role": "supporting_prop",
      "importance": 0.85,
      "appearance": {
        "shape": "mushroom_dome",
        "style": "minimalist_retro",
        "condition": "pristine",
        "pattern": null
      },
      "materials": [
        {
          "component": "body",
          "material": "polished_metal",
          "color": {"name": "silver", "hex": "#C0C0C0"},
          "finish": "reflective",
          "texture": "smooth"
        }
      ],
      "frame": {"center_x": 0.23, "center_y": 0.70, "width": 0.20, "height": 0.20, "rotation_deg": 0},
      "depth_plane": "foreground",
      "state": {"visible": true, "quantity": 1}
    },
    {
      "id": "object_red_floor_lamp_01",
      "type": "floor_lamp",
      "role": "decorative_prop",
      "importance": 0.45,
      "appearance": {
        "shape": "thin_stem_with_conical_shade",
        "style": "minimalist_retro",
        "condition": "pristine",
        "pattern": null
      },
      "materials": [
        {
          "component": "body",
          "material": "painted_metal",
          "color": {"name": "rust_red", "hex": "#B84328"},
          "finish": "matte",
          "texture": "smooth"
        }
      ],
      "frame": {"center_x": 0.20, "center_y": 0.30, "width": 0.10, "height": 0.38, "rotation_deg": 0},
      "depth_plane": "midground",
      "state": {"visible": true, "quantity": 1}
    },
    {
      "id": "object_olive_lamp_01",
      "type": "studio_lamp_prop",
      "role": "decorative_prop",
      "importance": 0.35,
      "appearance": {
        "shape": "cone_shade_on_c_stand",
        "style": "studio_prop",
        "condition": "pristine",
        "pattern": null
      },
      "materials": [
        {
          "component": "shade",
          "material": "painted_metal",
          "color": {"name": "olive_green", "hex": "#556B2F"},
          "finish": "matte",
          "texture": "smooth"
        }
      ],
      "frame": {"center_x": 0.80, "center_y": 0.28, "width": 0.14, "height": 0.35, "rotation_deg": 0},
      "depth_plane": "background",
      "state": {"visible": true, "quantity": 1}
    },
    {
      "id": "object_backdrop_01",
      "type": "fabric_backdrop",
      "role": "environmental",
      "importance": 0.55,
      "appearance": {
        "shape": "draped_rectangular_fabric",
        "style": "painted_studio_backdrop",
        "condition": "wrinkled",
        "pattern": "abstract_cloud_sky"
      },
      "materials": [
        {
          "component": "fabric",
          "material": "textile",
          "color": {"name": "slate_blue_and_off_white", "hex": null},
          "finish": "matte",
          "texture": "wrinkled"
        }
      ],
      "frame": {"center_x": 0.32, "center_y": 0.26, "width": 0.46, "height": 0.36, "rotation_deg": 0},
      "depth_plane": "background",
      "state": {"visible": true, "quantity": 1}
    },
    {
      "id": "object_carrots_01",
      "type": "carrots",
      "role": "decorative_prop",
      "importance": 0.20,
      "appearance": {"shape": "natural", "style": "unstyled_food_prop", "condition": "fresh", "pattern": null},
      "materials": [],
      "frame": {"center_x": 0.40, "center_y": 0.58, "width": 0.08, "height": 0.06, "rotation_deg": 15},
      "depth_plane": "midground",
      "state": {"visible": true, "quantity": 2}
    },
    {
      "id": "object_snack_01",
      "type": "snack",
      "role": "interaction_prop",
      "importance": 0.30,
      "appearance": {"shape": "small_handheld_food_item", "style": "natural", "condition": "partially_eaten", "pattern": null},
      "materials": [],
      "frame": {"center_x": 0.66, "center_y": 0.46, "width": 0.04, "height": 0.04, "rotation_deg": 0},
      "depth_plane": "midground",
      "state": {"visible": true, "quantity": 1}
    }
  ],

  "surfaces": [
    {
      "id": "surface_wall_01",
      "type": "wall",
      "role": "background_surface",
      "material": "plaster",
      "color": {"name": "golden_ochre", "hex": "#D9AA55"},
      "finish": "matte",
      "texture": "rough_weathered",
      "condition": "aged",
      "features": ["subtle_scuffs", "patchy_tonal_variation", "slight_weathering"]
    },
    {
      "id": "surface_ground_01",
      "type": "ground",
      "role": "floor_surface",
      "material": "grass",
      "color": {"name": "grass_green", "hex": "#556B2F"},
      "finish": "natural",
      "texture": "organic",
      "condition": "healthy",
      "features": ["sunlit_yellow_green_patches"]
    }
  ],

  "relationships": [
    {"source_id": "subject_child_01", "relation": "seated_on", "target_id": "object_sofa_01", "strength": "hard"},
    {"source_id": "subject_child_01", "relation": "holding", "target_id": "object_snack_01", "strength": "hard"},
    {"source_id": "object_table_lamp_01", "relation": "resting_on", "target_id": "object_coffee_table_01", "strength": "hard"},
    {"source_id": "object_carrots_01", "relation": "resting_on", "target_id": "object_sofa_01", "strength": "soft"},
    {"source_id": "object_backdrop_01", "relation": "in_front_of", "target_id": "surface_wall_01", "strength": "hard"}
  ],

  "lighting": {
    "environment": "outdoor",
    "overall_style": "hard_directional_sun",
    "sources": [
      {
        "id": "light_sun_01",
        "type": "sun",
        "role": "key",
        "enabled": true,
        "intensity": 1.0,
        "direction": {"azimuth_deg": 315, "elevation_deg": 45},
        "color_temperature_k": 5500,
        "hardness": 0.90,
        "shadow_strength": 0.90
      }
    ],
    "ambient": {"intensity": 0.12, "color_temperature_k": 6500},
    "shadow_style": {"edge_hardness": 0.90, "density": 0.85},
    "highlight_targets": [
      "subject_child_01.appearance.hair",
      "object_table_lamp_01",
      "object_sofa_01"
    ]
  },

  "camera": {
    "projection": "perspective",
    "view": {
      "shot_size": "medium_wide",
      "angle": "slightly_high",
      "pitch_deg": -8,
      "yaw_deg": 0,
      "roll_deg": 0,
      "camera_height": "slightly_above_subject_eye_level"
    },
    "lens": {
      "focal_length_mm": 21,
      "aperture_f": 4.0,
      "lens_character": "wide_angle_editorial"
    },
    "focus": {
      "target_id": "subject_child_01",
      "depth_of_field": "medium",
      "focus_falloff": "gradual"
    },
    "exposure": {
      "iso": 100,
      "shutter_speed_s": 0.001,
      "white_balance_k": 5500
    }
  },

  "color": {
    "palette_strategy": "complementary_warm_cool",
    "palette": [
      {"name": "slate_blue", "hex": "#8DA7BE", "target_coverage": 0.22, "role": "primary_cool"},
      {"name": "off_white", "hex": "#F2EFE6", "target_coverage": 0.13, "role": "neutral"},
      {"name": "golden_ochre", "hex": "#D9AA55", "target_coverage": 0.25, "role": "primary_warm"},
      {"name": "terracotta", "hex": "#B84328", "target_coverage": 0.15, "role": "accent"},
      {"name": "grass_green", "hex": "#556B2F", "target_coverage": 0.20, "role": "environment"},
      {"name": "copper_ginger", "hex": "#C85A24", "target_coverage": 0.05, "role": "subject_accent"}
    ],
    "global_temperature": 0.68,
    "saturation": 0.65,
    "contrast": 0.80
  },

  "style": {
    "primary_style": "editorial_lifestyle_photography",
    "references": [
      {"name": "1970s_campaign_photography", "weight": 0.85},
      {"name": "surrealist_outdoor_studio_set", "weight": 0.55},
      {"name": "contemporary_european_lifestyle_advertising", "weight": 0.75}
    ],
    "medium": "photographic",
    "texture_character": "organic_filmic",
    "image_cleanliness": 0.65,
    "film_character": {
      "enabled": true,
      "grain_strength": 0.22,
      "grain_size": "fine",
      "halation": 0.08
    }
  },

  "typography": {
    "enabled": true,
    "elements": [
      {
        "id": "text_brand_01",
        "content": "THE MASIE",
        "role": "brand",
        "frame": {"center_x": 0.50, "center_y": 0.06, "width": 0.30, "height": 0.05},
        "font": {"family_class": "sans_serif", "weight": 500, "style": "modern"},
        "alignment": "center",
        "preserve_exact_text": true
      }
    ]
  },

  "post_processing": {
    "exposure_adjustment": 0.00,
    "midtone_contrast": 0.15,
    "highlight_recovery": 0.05,
    "shadow_lift": 0.00,
    "temperature_shift": 0.12,
    "tint_shift": 0.00,
    "saturation_adjustment": 0.10,
    "sharpness": 0.20,
    "vignette": 0.00,
    "skin_smoothing": 0.00
  },

  "constraints": {
    "hard": [
      {"type": "relationship", "source_id": "subject_child_01", "relation": "seated_on", "target_id": "object_sofa_01"},
      {"type": "relationship", "source_id": "subject_child_01", "relation": "holding", "target_id": "object_snack_01"},
      {
        "type": "property",
        "path": "/canvas/aspect_ratio",
        "operator": "equals",
        "value": {"width": 2, "height": 3}
      },
      {"type": "semantic", "instruction": "Preserve exactly one primary child subject."},
      {"type": "semantic", "instruction": "Preserve copper ginger hair."},
      {"type": "semantic", "instruction": "Preserve the blue-and-off-white striped sofa with terracotta tubular frame."},
      {"type": "semantic", "instruction": "Preserve hard directional sunlight and deep defined shadows."}
    ],
    "soft": [
      {"type": "entity", "entity_id": "object_carrots_01", "weight": 0.35},
      {"type": "entity", "entity_id": "object_olive_lamp_01", "weight": 0.50},
      {"type": "entity", "entity_id": "object_backdrop_01", "weight": 0.70}
    ],
    "negative": [
      {"type": "semantic", "instruction": "No additional people."},
      {"type": "semantic", "instruction": "Avoid malformed or duplicated limbs, hands, or fingers."},
      {"type": "semantic", "instruction": "Avoid plastic-looking skin or excessive beauty retouching."},
      {"type": "semantic", "instruction": "Avoid soft overcast lighting."},
      {"type": "semantic", "instruction": "Avoid indoor-room interpretation."},
      {"type": "semantic", "instruction": "Avoid generic corporate stock-photography aesthetics."}
    ]
  }
}
```

---

## 2. Core Conventions

### 2.1 Normalized values

Use values between `0.0` and `1.0` for subjective intensity-style properties.

| Value | General meaning |
|---:|---|
| `0.0` | none / minimum |
| `0.25` | low |
| `0.5` | moderate |
| `0.75` | high |
| `1.0` | maximum |

Use real physical units where they exist instead of normalizing them, for example `focal_length_mm`, `aperture_f`, `color_temperature_k`, `azimuth_deg`, and `elevation_deg`.

### 2.2 Frame coordinates

All subjects, objects, and typography use the same normalized coordinate system: `x=0` left, `x=1` right, `y=0` top, `y=1` bottom. `width` and `height` are fractions of the total frame.

```json
"frame": {
  "center_x": 0.67,
  "center_y": 0.52,
  "width": 0.27,
  "height": 0.40,
  "rotation_deg": 0
}
```

Treat these as composition targets rather than guaranteed pixel-perfect bounding boxes.

### 2.3 IDs

Every independently referenceable element should have a stable ID. Recommended prefixes are `subject_`, `object_`, `surface_`, `light_`, and `text_`. Do not rely on array positions as permanent identifiers.

---

## 3. Section Guide and Suggested Values

### `metadata`

Organization and retrieval only. Do not place visual parameters here.

Typical `purpose` values: `marketing`, `advertising`, `editorial`, `product`, `fashion`, `portrait`, `social_media`, `concept_art`, `ecommerce`, `documentary`, `personal`, `other`.

### `canvas`

Owns image dimensions and crop behavior.

`orientation`: `portrait`, `landscape`, `square`.

`crop_policy`: `flexible`, `preserve_primary_subject`, `preserve_primary_focal_points`, `preserve_all_entities`, `center_crop`, `no_crop`.

### `creative_direction`

Owns high-level creative intent only. Typical `genre` values: `editorial_commercial`, `fashion_editorial`, `lifestyle`, `product_photography`, `documentary`, `portrait`, `street_photography`, `cinematic`, `fine_art`, `surrealist`, `architectural`, `food_photography`.

Mood examples: `playful`, `serene`, `dramatic`, `intimate`, `energetic`, `premium`, `nostalgic`, `melancholic`, `luxurious`, `minimal`, `whimsical`, `raw`, `candid`, `formal`.

`era_reference` can be `null`, `1960s`, `1970s`, `1980s`, `1990s`, `early_2000s`, or `contemporary`.

### `composition`

Owns overall frame organization, not individual entity appearance.

`layout` examples: `single_subject`, `multi_subject`, `single_product`, `multi_product`, `multi_element`, `environmental`, `layered`, `flat_lay`, `symmetrical_centered`, `diagonal`, `editorial_collage`.

`balance` examples: `symmetric`, `asymmetric`, `radial`, `center_weighted`, `left_weighted`, `right_weighted`, `top_weighted`, `bottom_weighted`, `dynamic`.

`negative_space.preferred_regions`: `top`, `bottom`, `left`, `right`, `center`, `top_left`, `top_center`, `top_right`, `center_left`, `center_right`, `bottom_left`, `bottom_center`, `bottom_right`.

### `subjects[]`

Use for people, animals, fictional characters, or other animate subjects.

Recommended `role`: `primary`, `secondary`, `supporting`, `background`.

Recommended `age_group`: `infant`, `toddler`, `young_child`, `older_child`, `teen`, `young_adult`, `adult`, `middle_aged`, `older_adult`.

Hair examples: lengths `buzzed`, `short`, `chin_length`, `shoulder_length`, `mid_back`, `waist_length`; textures `straight`, `wavy`, `curly`, `coily`; styling `natural_unstyled`, `sleek`, `messy`, `braided`, `ponytail`, `bun`, `wet_look`, `windswept`.

Pose `posture`: `standing`, `seated`, `lying`, `crouching`, `kneeling`, `walking`, `running`, `leaning`.

Expression style: `candid`, `posed`, `neutral`, `subtle`, `exaggerated`, `editorial`, `natural`.

Hand visibility: `visible`, `partially_visible`, `mostly_hidden`, `hidden`. Hand actions: `resting`, `holding`, `touching`, `pointing`, `gripping`, `supporting`, `raised`, `open`, `closed`.

### `objects[]`

Use for discrete physical entities such as furniture, props, food, vehicles, tools, lamps, and backdrops.

Recommended `role`: `hero_product`, `supporting_product`, `interaction_prop`, `supporting_prop`, `decorative_prop`, `environmental`, `background_detail`.

`importance` represents preservation priority, not visual size: approximately `1.0` essential, `0.75` highly important, `0.5` useful, `0.25` minor detail, `0.0` disposable.

Common `condition`: `new`, `pristine`, `clean`, `used`, `weathered`, `aged`, `worn`, `damaged`, `rusted`, `wrinkled`, `fresh`, `partially_eaten`.

Material examples: `wood`, `painted_metal`, `polished_metal`, `steel`, `aluminum`, `glass`, `plastic`, `ceramic`, `stone`, `concrete`, `plaster`, `fabric`, `textile`, `leather`, `paper`, `rubber`, `grass`, `water`.

Finish examples: `matte`, `satin`, `gloss`, `high_gloss`, `polished`, `reflective`, `brushed`, `raw`, `weathered`, `translucent`, `transparent`.

Texture examples: `smooth`, `rough`, `woven`, `slatted`, `brushed`, `grainy`, `wrinkled`, `ribbed`, `porous`, `distressed`.

### `surfaces[]`

Use for continuous environmental planes or regions such as wall, floor, grass, road, sky, ceiling, water, sand, or façade. Do not create a separate `background` object purely because something sits behind the subject; background is positional, not a type.

### `relationships[]`

Use structured relationships to encode entity interactions.

Spatial: `left_of`, `right_of`, `above`, `below`, `behind`, `in_front_of`, `inside`, `outside`, `adjacent_to`, `overlapping`, `surrounding`.

Physical: `on`, `under`, `resting_on`, `attached_to`, `touching`, `holding`, `wearing`, `carrying`, `supporting`.

Pose: `seated_on`, `standing_on`, `leaning_on`, `kneeling_on`, `lying_on`.

Attention: `looking_at`, `facing`, `pointing_at`.

Lighting: `illuminated_by`, `emitted_by`, `reflecting`.

`strength`: `hard` or `soft`.

### `lighting`

Owns actual illumination only. A visible lamp remains an object unless it materially lights the scene.

`environment`: `outdoor`, `indoor`, `studio`, `mixed`, `night_exterior`, `day_exterior`, `window_lit_interior`.

Light `type`: `sun`, `sky`, `window`, `softbox`, `spotlight`, `led_panel`, `practical_lamp`, `flash`, `bounce`, `reflector`, `rim_light`, `ambient`, `unknown`.

Light `role`: `key`, `fill`, `rim`, `backlight`, `accent`, `practical`, `ambient`.

Color temperature guide: `2000–3000K` very warm/tungsten, `3200K` tungsten studio, `4000K` warm-neutral, `5000–5600K` daylight, `6500K` cool daylight, `7500K+` strongly cool.

### `camera`

Owns view geometry, lens, focus, and exposure. Do not place grain, mood, or color grading here.

`projection`: `perspective`, `orthographic`, `fisheye`, `panoramic`.

`shot_size`: `extreme_close_up`, `close_up`, `medium_close_up`, `medium`, `medium_wide`, `wide`, `extreme_wide`, `full_body`, `three_quarter`.

`angle`: `eye_level`, `slightly_high`, `high_angle`, `overhead`, `slightly_low`, `low_angle`, `ground_level`, `dutch_angle`.

Typical full-frame-like lens feel: `14–20mm` ultra-wide, `21–28mm` wide environmental, `35mm` documentary/editorial, `50mm` natural, `85mm` portrait, `105–135mm` compressed portrait, `200mm+` strong compression.

`depth_of_field`: `very_shallow`, `shallow`, `medium`, `deep`, `very_deep`.

`focus_falloff`: `abrupt`, `moderate`, `gradual`.

Exposure values may function as photographic guidance rather than physically exact simulation depending on the generation model.

### `color`

Owns the global palette and global color treatment. Object-specific colors stay under each object's `materials[]`.

`palette_strategy`: `monochromatic`, `analogous`, `complementary`, `split_complementary`, `triadic`, `tetradic`, `warm_dominant`, `cool_dominant`, `neutral_with_accents`, `complementary_warm_cool`, `custom`.

Palette `role`: `primary`, `secondary`, `accent`, `neutral`, `environment`, `subject_accent`, `primary_warm`, `primary_cool`.

`target_coverage` is optional and approximate; coverage values do not need to sum exactly to `1.0`.

### `style`

Owns artistic and photographic visual language.

`primary_style` examples: `editorial_lifestyle_photography`, `commercial_product_photography`, `documentary_photography`, `fashion_editorial`, `cinematic_still`, `fine_art_photography`, `surrealist_editorial`, `minimalist_product`, `luxury_campaign`, `street_photography`.

`medium`: `photographic`, `digital_photography`, `35mm_film_emulation`, `medium_format_emulation`, `illustration`, `painting`, `3d_render`, `mixed_media`.

Reference weight guideline: `0.25` subtle, `0.50` moderate, `0.75` strong, `1.0` dominant.

Film grain size: `very_fine`, `fine`, `medium`, `coarse`.

### `typography`

Use only when text should visibly appear in the image.

Font family class: `sans_serif`, `serif`, `monospace`, `display`, `script`, `handwritten`, `blackletter`.

Common numeric weights: `100` thin, `200` extra light, `300` light, `400` regular, `500` medium, `600` semi-bold, `700` bold, `800` extra-bold, `900` black.

Alignment: `left`, `center`, `right`, `justified`.

### `post_processing`

Owns changes conceptually applied after capture. Use signed adjustment values from `-1.0` to `+1.0`, where `0.0` is neutral. Avoid duplicating grain here if `style.film_character.grain_strength` already owns grain.

### `constraints`

Use `hard` for requirements that should not vary, `soft` for weighted preferences, and `negative` for unwanted interpretations or common generation failure modes.

Property constraint operators may include `equals`, `not_equals`, `greater_than`, `less_than`, `greater_than_or_equal`, `less_than_or_equal`, `contains`, and `one_of`.

Prefer structured constraints where possible. Use semantic text only where the requirement cannot be represented cleanly as an entity, relationship, or property constraint.

---

## 4. Avoiding Duplication

Use this ownership table as the canonical rule.

| Property | Canonical section |
|---|---|
| Aspect ratio | `canvas` |
| Overall creative mood | `creative_direction` |
| Visual hierarchy | `composition` |
| Person appearance | `subjects` |
| Person pose/expression | `subjects` |
| Furniture and props | `objects` |
| Wall, floor, grass, sky | `surfaces` |
| Entity interactions | `relationships` |
| Actual illumination | `lighting` |
| Camera angle and optics | `camera` |
| Global palette | `color` |
| Object-specific color/material | `objects.materials` |
| Artistic photographic language | `style` |
| Visible text | `typography` |
| Grading/sharpness | `post_processing` |
| Must / prefer / avoid rules | `constraints` |

Example of duplication to avoid:

```text
BAD
creative_direction.mood = "warm"
lighting.mood = "warm"
style.mood = "warm"

BETTER
creative_direction.primary_mood = "playful"
lighting.sources[0].color_temperature_k = 5500
color.global_temperature = 0.68
```

---

## 5. Sparse Instances Are Recommended

The schema supports fine-grained control, but an image does not need every field. Add precision only where it matters.

```json
{
  "id": "object_book_01",
  "type": "book",
  "role": "decorative_prop",
  "importance": 0.2,
  "frame": {
    "center_x": 0.35,
    "center_y": 0.75,
    "width": 0.08,
    "height": 0.04,
    "rotation_deg": 12
  },
  "depth_plane": "foreground",
  "state": {
    "visible": true,
    "quantity": 1
  }
}
```

Only specify materials, textures, exact colors, condition, or geometry when they are relevant to the output.

---

## 6. Recommended Validation Rules

### IDs

- IDs must be unique.
- Relationship IDs must reference existing entities.
- Focus targets must reference an existing entity.
- Highlight targets should reference valid entities or valid sub-properties.

### Normalized numeric bounds

```text
importance:           0.0–1.0
realism:              0.0–1.0
stylization:          0.0–1.0
candidness:           0.0–1.0
premium_feel:         0.0–1.0
frame center_x/y:     0.0–1.0
frame width/height:   0.0–1.0
light intensity:      0.0–1.0
hardness:             0.0–1.0
shadow_strength:      0.0–1.0
color saturation:     0.0–1.0
color contrast:       0.0–1.0
style weights:        0.0–1.0
```

Post-processing adjustment fields should normally use `-1.0–1.0`.

### Physical parameters

Recommended sanity ranges:

```text
focal_length_mm:       > 0
aperture_f:            > 0
iso:                   > 0
shutter_speed_s:       > 0
color_temperature_k:   1000–20000
azimuth_deg:            0–359
elevation_deg:         -90–90
```

---

## 7. Recommended Generation Workflow

The JSON should remain the canonical representation.

```text
Scene JSON
   ↓
Validation
   ↓
Prompt / request compiler
   ↓
Model-specific adapter
   ↓
Image-generation model
   ↓
Generated image
```

Do not manually maintain a long prose prompt that repeats the entire JSON. Generate model-specific instructions from the structured specification instead. This avoids conflicts such as a JSON lens value of `21mm` while a prose prompt independently says `35mm`, or hard midday sunlight in one place and soft golden-hour light in another.

---

## 8. Optional Future Extensions

The base schema is intentionally focused on generating one image as-is. Potential future extensions include:

```text
identity_reference
image_reference
mask_reference
regional_prompting
control_points
pose_skeleton
depth_map
camera_extrinsics
camera_intrinsics
object_segmentation
material_physics
reflection_control
motion
weather
time_of_day
model_adapter
generation_seed
variation_controls
```

Add these only when the target model or pipeline can make meaningful use of them.

---

## 9. Design Rule

> **Every visual property should be editable precisely, but no property should require precise editing.**

The JSON represents the most detailed canonical image state. A UI can expose simpler high-level controls above it while expert users retain direct access to the full specification.
