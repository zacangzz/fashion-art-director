import { useState, useCallback } from 'react';
import { getBaseResolution } from '../components/BaselineSelector';
import { composeProps } from '../services/apiClient';
import { PROP_SCALE_PRESETS } from '../constants/propCategories';

/**
 * Hook for managing Step 4: Scene Studio -> Prop Placement and Composition.
 */
export function usePropComposer({
  visionModel,
  imagenModel,
  aspectRatio,
  onAspectRatioChange,
  generationResult,
  activeBaseline,
  activeSeed,
  seedMode,
  conversationId,
  setPreviousGenerationResult,
  setGenerationResult,
  setActiveSeed,
  setConversationId,
  setConversationMessages,
  onError,
  onHistoryRefresh,
}) {
  const [propAssignments, setPropAssignments] = useState([]);
  const [isComposingProps, setIsComposingProps] = useState(false);

  const handleAddPropAssignment = useCallback((propItem, dropPosition = { x: 0.5, y: 0.5 }) => {
    if (!propItem) return;
    setPropAssignments((prev) => {
      const nextPin = prev.length + 1;
      const defaultPreset = PROP_SCALE_PRESETS[1]; // medium (0.30)
      const halfSize = defaultPreset.factor / 2;

      // Center the bounding box around dropPosition, clamped to [0, 1]
      const x = Math.max(halfSize, Math.min(1 - halfSize, dropPosition.x ?? 0.5));
      const y = Math.max(halfSize, Math.min(1 - halfSize, dropPosition.y ?? 0.5));

      const newAsgn = {
        prop_item_id: propItem.id,
        pin_number: nextPin,
        bounding_box: {
          ymin: Math.max(0, y - halfSize),
          xmin: Math.max(0, x - halfSize),
          ymax: Math.min(1, y + halfSize),
          xmax: Math.min(1, x + halfSize),
        },
        scale_preset: defaultPreset.id,
        scale_factor: defaultPreset.factor,
        item_label: propItem.label || 'Prop Item',
        category: propItem.category || 'decor',
        notes: '',
        aspect_ratio: propItem.aspect_ratio || 1.0,
      };
      return [...prev, newAsgn];
    });
  }, []);

  const handleUpdatePropBox = useCallback((pinNumber, newBox) => {
    setPropAssignments((prev) =>
      prev.map((a) => (a.pin_number === pinNumber ? { ...a, bounding_box: newBox } : a))
    );
  }, []);

  const handleUpdatePropScale = useCallback((pinNumber, scalePresetId) => {
    const preset = PROP_SCALE_PRESETS.find((p) => p.id === scalePresetId) || PROP_SCALE_PRESETS[1];
    setPropAssignments((prev) =>
      prev.map((a) => {
        if (a.pin_number !== pinNumber) return a;
        const box = a.bounding_box;
        const centerX = (box.xmin + box.xmax) / 2;
        const centerY = (box.ymin + box.ymax) / 2;
        const halfSize = preset.factor / 2;
        return {
          ...a,
          scale_preset: preset.id,
          scale_factor: preset.factor,
          bounding_box: {
            ymin: Math.max(0, centerY - halfSize),
            xmin: Math.max(0, centerX - halfSize),
            ymax: Math.min(1, centerY + halfSize),
            xmax: Math.min(1, centerX + halfSize),
          },
        };
      })
    );
  }, []);

  const handleUpdatePropNotes = useCallback((pinNumber, notes) => {
    setPropAssignments((prev) =>
      prev.map((a) => (a.pin_number === pinNumber ? { ...a, notes } : a))
    );
  }, []);

  const handleRemovePropAssignment = useCallback((pinNumber) => {
    setPropAssignments((prev) => {
      const filtered = prev.filter((a) => a.pin_number !== pinNumber);
      return filtered.map((a, idx) => ({ ...a, pin_number: idx + 1 }));
    });
  }, []);

  const handleClearPropAssignments = useCallback(() => {
    setPropAssignments([]);
  }, []);

  const handleComposeProps = useCallback(async (customInstruction = '') => {
    if (propAssignments.length === 0) return;

    setIsComposingProps(true);
    onError?.(null);

    const parentId = generationResult?.generation_id || activeBaseline?.id;
    const effSeed = seedMode === 'locked' ? activeSeed : Math.floor(Math.random() * 9000000) + 1000000;
    const effRatio = aspectRatio || generationResult?.aspect_ratio || activeBaseline?.aspect_ratio || '1:1';

    try {
      const payload = {
        parent_id: parentId,
        assignments: propAssignments.map((a) => ({
          prop_item_id: a.prop_item_id,
          pin_number: a.pin_number,
          bounding_box: a.bounding_box,
          scale_preset: a.scale_preset,
          scale_factor: a.scale_factor,
          item_label: a.item_label,
          notes: a.notes,
        })),
        seed: effSeed,
        seed_mode: seedMode,
        aspect_ratio: effRatio,
        conversation_id: conversationId,
        custom_instruction: customInstruction,
        imagen_model: imagenModel,
        vision_model: visionModel,
      };

      const result = await composeProps(payload);

      if (generationResult) {
        setPreviousGenerationResult(generationResult);
      }

      const resRatio = result.aspect_ratio || effRatio;
      const nextGen = {
        generation_id: result.generation_id,
        master_image_url: result.image_url,
        seed: result.seed,
        compiled_prompt: result.compiled_prompt,
        aspect_ratio: resRatio,
        resolution: result.resolution || getBaseResolution(resRatio),
      };
      setGenerationResult(nextGen);
      setActiveSeed(result.seed);

      if (result.aspect_ratio && onAspectRatioChange) {
        onAspectRatioChange(result.aspect_ratio);
      }

      if (result.conversation_id && !conversationId) {
        setConversationId(result.conversation_id);
      }

      const newMsg = {
        role: 'user',
        prompt:
          `Prop Placement (${propAssignments.length} item${propAssignments.length !== 1 ? 's' : ''}): ` +
          propAssignments.map((a) => `#${a.pin_number} ${a.item_label}`).join(', '),
        generation_id: result.generation_id,
        image_url: result.image_url,
        seed: result.seed,
        created_at: result.created_at || new Date().toISOString(),
        aspect_ratio: resRatio,
        is_prop: true,
      };
      setConversationMessages((prev) => [...prev, newMsg]);

      setPropAssignments([]);
      await onHistoryRefresh?.();
    } catch (err) {
      onError?.(err.message || 'Prop composition failed.');
    } finally {
      setIsComposingProps(false);
    }
  }, [
    propAssignments,
    generationResult,
    activeBaseline?.id,
    activeBaseline?.aspect_ratio,
    seedMode,
    activeSeed,
    aspectRatio,
    onAspectRatioChange,
    conversationId,
    imagenModel,
    visionModel,
    onError,
    setPreviousGenerationResult,
    setGenerationResult,
    setActiveSeed,
    setConversationId,
    setConversationMessages,
    onHistoryRefresh,
  ]);

  return {
    propAssignments,
    setPropAssignments,
    isComposingProps,
    handleAddPropAssignment,
    handleUpdatePropBox,
    handleUpdatePropScale,
    handleUpdatePropNotes,
    handleRemovePropAssignment,
    handleClearPropAssignments,
    handleComposeProps,
  };
}
