import { useState, useCallback } from 'react';
import { getBaseResolution } from '../components/BaselineSelector';
import { refineGeneration, exportBundle } from '../services/apiClient';

/**
 * Hook for managing Step 2: Conversational Refinement, generations lineage, and seeds.
 */
export function useRefinementStudio({ imagenModel, aspectRatio, onAspectRatioChange, activeBaseline, onError, onHistoryRefresh }) {
  const [conversationId, setConversationId] = useState(null);
  const [conversationMessages, setConversationMessages] = useState([]);
  const [generationResult, setGenerationResult] = useState(null);
  const [previousGenerationResult, setPreviousGenerationResult] = useState(null);
  const [activeSeed, setActiveSeed] = useState(4289102);
  const [seedMode, setSeedMode] = useState('locked');
  const [isGenerating, setIsGenerating] = useState(false);
  const [isInpainting, setIsInpainting] = useState(false);
  const [isExporting, setIsExporting] = useState(false);

  // Send Refinement Prompt
  const handleSendRefinement = useCallback(async (promptText, bgOptions = {}) => {
    if (!promptText || !promptText.trim()) return;

    setIsGenerating(true);
    onError?.(null);

    const parentId = generationResult?.generation_id || activeBaseline?.id;
    const effSeed = seedMode === 'locked' ? activeSeed : Math.floor(Math.random() * 9000000) + 1000000;
    const effRatio = aspectRatio || generationResult?.aspect_ratio || activeBaseline?.aspect_ratio || '1:1';

    try {
      const payload = {
        parent_id: parentId,
        prompt: promptText.trim(),
        seed: effSeed,
        seed_mode: seedMode,
        aspect_ratio: effRatio,
        conversation_id: conversationId,
        imagen_model: imagenModel,
        background_reference_id: bgOptions.background_reference_id || undefined,
        perspective_mode: bgOptions.perspective_mode || undefined,
        depth_of_field: bgOptions.depth_of_field || undefined,
        lighting_mode: bgOptions.lighting_mode || undefined,
      };

      const result = await refineGeneration(payload);

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
        background_reference_id: result.background_reference_id,
        background_harmonization_meta: result.background_harmonization_meta,
      };
      setGenerationResult(nextGen);
      setActiveSeed(result.seed);

      if (result.aspect_ratio && onAspectRatioChange) {
        onAspectRatioChange(result.aspect_ratio);
      }

      if (result.conversation_id && !conversationId) {
        setConversationId(result.conversation_id);
      }

      // Append new message
      const newMsg = {
        role: 'user',
        prompt: promptText.trim(),
        generation_id: result.generation_id,
        image_url: result.image_url,
        seed: result.seed,
        created_at: result.created_at || new Date().toISOString(),
        aspect_ratio: resRatio,
        background_reference_id: result.background_reference_id || bgOptions.background_reference_id,
        background_reference_url: bgOptions.background_reference_url,
        background_harmonization_meta: result.background_harmonization_meta || (bgOptions.background_reference_id ? {
          perspective_mode: bgOptions.perspective_mode,
          depth_of_field: bgOptions.depth_of_field,
          lighting_mode: bgOptions.lighting_mode,
        } : undefined),
      };
      setConversationMessages((prev) => [...prev, newMsg]);

      await onHistoryRefresh?.();
    } catch (err) {
      onError?.(err.message || 'Refinement generation failed.');
    } finally {
      setIsGenerating(false);
    }
  }, [generationResult, activeBaseline?.id, activeBaseline?.aspect_ratio, seedMode, activeSeed, aspectRatio, conversationId, imagenModel, onAspectRatioChange, onError, onHistoryRefresh]);

  // Select message in chat lineage thread
  const handleSelectMessage = useCallback((msg) => {
    if (!msg || !msg.generation_id) return;
    if (generationResult && generationResult.generation_id !== msg.generation_id) {
      setPreviousGenerationResult(generationResult);
    }
    const effRatio = msg.aspect_ratio || generationResult?.aspect_ratio || aspectRatio || '1:1';
    setGenerationResult({
      generation_id: msg.generation_id,
      master_image_url: msg.image_url,
      seed: msg.seed,
      compiled_prompt: msg.prompt,
      aspect_ratio: effRatio,
      resolution: msg.resolution || getBaseResolution(effRatio),
    });
    setActiveSeed(msg.seed);
    if (msg.aspect_ratio && onAspectRatioChange) {
      onAspectRatioChange(msg.aspect_ratio);
    }
  }, [generationResult, aspectRatio, onAspectRatioChange]);

  // Inpaint completion handler
  const handleInpaintComplete = useCallback(async (result) => {
    if (!result) return;
    if (generationResult) {
      setPreviousGenerationResult(generationResult);
    }
    const effRatio = result.aspect_ratio || generationResult?.aspect_ratio || aspectRatio || '1:1';
    const nextGen = {
      generation_id: result.generation_id,
      master_image_url: result.image_url,
      seed: result.seed,
      compiled_prompt: result.compiled_prompt,
      aspect_ratio: effRatio,
      resolution: result.resolution || getBaseResolution(effRatio),
    };
    setGenerationResult(nextGen);

    if (result.aspect_ratio && onAspectRatioChange) {
      onAspectRatioChange(result.aspect_ratio);
    }

    const inpaintMsg = {
      role: 'user',
      prompt: `[Inpaint Edit] ${result.compiled_prompt}`,
      generation_id: result.generation_id,
      image_url: result.image_url,
      seed: result.seed,
      created_at: result.created_at || new Date().toISOString(),
      aspect_ratio: effRatio,
    };
    setConversationMessages((prev) => [...prev, inpaintMsg]);

    await onHistoryRefresh?.();
  }, [generationResult, aspectRatio, onAspectRatioChange, onHistoryRefresh]);

  // Export Bundle ZIP download
  const handleExportBundle = useCallback(async (genId) => {
    const targetId = genId || generationResult?.generation_id || activeBaseline?.id;
    if (!targetId) return;

    setIsExporting(true);
    onError?.(null);
    try {
      const blob = await exportBundle(targetId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `bundle_${targetId}.zip`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      onError?.(err.message || 'Failed to download export bundle.');
    } finally {
      setIsExporting(false);
    }
  }, [generationResult?.generation_id, activeBaseline?.id, onError]);

  return {
    conversationId,
    setConversationId,
    conversationMessages,
    setConversationMessages,
    generationResult,
    setGenerationResult,
    previousGenerationResult,
    setPreviousGenerationResult,
    activeSeed,
    setActiveSeed,
    seedMode,
    setSeedMode,
    isGenerating,
    setIsGenerating,
    isInpainting,
    setIsInpainting,
    isExporting,
    handleSendRefinement,
    handleSelectMessage,
    handleInpaintComplete,
    handleExportBundle,
  };
}
