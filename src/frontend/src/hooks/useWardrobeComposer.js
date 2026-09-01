import { useState, useCallback } from 'react';
import { getBaseResolution } from '../components/BaselineSelector';
import { composeWardrobe } from '../services/apiClient';

/**
 * Hook for managing Step 4: Wardrobe Composition Studio and garment pin placements.
 */
export function useWardrobeComposer({
  visionModel,
  imagenModel,
  aspectRatio,
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
  const [wardrobeAssignments, setWardrobeAssignments] = useState([]);
  const [isComposingWardrobe, setIsComposingWardrobe] = useState(false);

  const handleAddWardrobeAssignment = useCallback((garmentItem, dropPosition) => {
    if (!garmentItem) return;
    setWardrobeAssignments((prev) => {
      const nextPin = prev.length + 1;
      const newAsgn = {
        wardrobe_item_id: garmentItem.id,
        pin_number: nextPin,
        drop_position: dropPosition || { x: 0.5, y: 0.5 },
        item_label: garmentItem.label || 'Garment',
        category: garmentItem.category || 'tops',
      };
      return [...prev, newAsgn];
    });
  }, []);

  const handleUpdateWardrobePosition = useCallback((pinNumber, newPosition) => {
    setWardrobeAssignments((prev) =>
      prev.map((a) => (a.pin_number === pinNumber ? { ...a, drop_position: newPosition } : a))
    );
  }, []);

  const handleRemoveWardrobeAssignment = useCallback((pinNumber) => {
    setWardrobeAssignments((prev) => {
      const filtered = prev.filter((a) => a.pin_number !== pinNumber);
      return filtered.map((a, idx) => ({ ...a, pin_number: idx + 1 }));
    });
  }, []);

  const handleClearWardrobeAssignments = useCallback(() => {
    setWardrobeAssignments([]);
  }, []);

  const handleComposeWardrobe = useCallback(async (customInstruction = '') => {
    if (wardrobeAssignments.length === 0) return;

    setIsComposingWardrobe(true);
    onError?.(null);

    const parentId = generationResult?.generation_id || activeBaseline?.id;
    const effSeed = seedMode === 'locked' ? activeSeed : Math.floor(Math.random() * 9000000) + 1000000;
    const effRatio = generationResult?.aspect_ratio || activeBaseline?.aspect_ratio || aspectRatio;

    try {
      const payload = {
        parent_id: parentId,
        assignments: wardrobeAssignments.map((a) => ({
          wardrobe_item_id: a.wardrobe_item_id,
          pin_number: a.pin_number,
          drop_position: a.drop_position,
          target_description: a.item_label,
        })),
        seed: effSeed,
        seed_mode: seedMode,
        aspect_ratio: effRatio,
        conversation_id: conversationId,
        custom_instruction: customInstruction,
        imagen_model: imagenModel,
        vision_model: visionModel,
      };

      const result = await composeWardrobe(payload);

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

      if (result.conversation_id && !conversationId) {
        setConversationId(result.conversation_id);
      }

      const newMsg = {
        role: 'user',
        prompt:
          `Wardrobe Swap (${wardrobeAssignments.length} item${wardrobeAssignments.length !== 1 ? 's' : ''}): ` +
          wardrobeAssignments.map((a) => `#${a.pin_number} ${a.item_label}`).join(', '),
        generation_id: result.generation_id,
        image_url: result.image_url,
        seed: result.seed,
        created_at: result.created_at || new Date().toISOString(),
      };
      setConversationMessages((prev) => [...prev, newMsg]);

      setWardrobeAssignments([]);
      await onHistoryRefresh?.();
    } catch (err) {
      onError?.(err.message || 'Wardrobe composition failed.');
    } finally {
      setIsComposingWardrobe(false);
    }
  }, [
    wardrobeAssignments,
    generationResult,
    activeBaseline,
    seedMode,
    activeSeed,
    aspectRatio,
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
    wardrobeAssignments,
    setWardrobeAssignments,
    isComposingWardrobe,
    handleAddWardrobeAssignment,
    handleUpdateWardrobePosition,
    handleRemoveWardrobeAssignment,
    handleClearWardrobeAssignments,
    handleComposeWardrobe,
  };
}
