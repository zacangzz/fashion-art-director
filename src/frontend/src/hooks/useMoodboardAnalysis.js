import { useState, useCallback } from 'react';
import { DEFAULT_TAG_STATE } from '../utils/defaultTags';
import {
  analyzeMoodboard,
  generateBaselines,
  resyncPromptFromLevers,
  resyncLeversFromPrompt,
  checkPromptConflicts,
  uploadDirectPhoto,
} from '../services/apiClient';

/**
 * Hook for managing Step 1: Moodboard Ingestion, 9-category visual levers, and 4-baseline generation.
 */
export function useMoodboardAnalysis({ visionModel, imagenModel, onError, onBaselineReady, onDirectPhotoReady, onHistoryRefresh }) {
  const [files, setFiles] = useState([]);
  const [baselinePrompt, setBaselinePrompt] = useState('');
  const [aspectRatio, setAspectRatio] = useState('1.8:1');
  const [temperature, setTemperature] = useState(1.0);
  const [promptConflicts, setPromptConflicts] = useState([]);
  const [isCheckingConflicts, setIsCheckingConflicts] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isGeneratingBaselines, setIsGeneratingBaselines] = useState(false);
  const [isResyncingPrompt, setIsResyncingPrompt] = useState(false);
  const [isResyncingLevers, setIsResyncingLevers] = useState(false);
  const [isDirectUploading, setIsDirectUploading] = useState(false);
  const [moodboardId, setMoodboardId] = useState(null);
  const [masterPrompt, setMasterPrompt] = useState('');
  const [baselines, setBaselines] = useState([]);
  const [activeBaseline, setActiveBaseline] = useState(null);

  const [tagState, setTagState] = useState(DEFAULT_TAG_STATE);
  const [lockedCategories, setLockedCategories] = useState([]);
  const [baselineTagSnapshot, setBaselineTagSnapshot] = useState(null);

  // Direct Photo Ingestion (Skip Step 1 Art Direction)
  const handleDirectPhotoUpload = useCallback(async (file, detectedRatio) => {
    if (!file) return;
    setIsDirectUploading(true);
    onError?.(null);

    try {
      const response = await uploadDirectPhoto(file, detectedRatio || aspectRatio);
      const effRatio = response.aspect_ratio || detectedRatio || aspectRatio;

      const baselineObj = {
        id: response.generation_id,
        seed: response.seed,
        image_url: response.image_url,
        created_at: response.created_at,
        aspect_ratio: effRatio,
        resolution: response.resolution,
        compiled_prompt: response.compiled_prompt,
      };

      setActiveBaseline(baselineObj);
      if (response.aspect_ratio) {
        setAspectRatio(response.aspect_ratio);
      }

      onDirectPhotoReady?.(response, effRatio);
      await onHistoryRefresh?.();
    } catch (err) {
      onError?.(err.message || 'Direct photo upload failed.');
    } finally {
      setIsDirectUploading(false);
    }
  }, [aspectRatio, onError, onDirectPhotoReady, onHistoryRefresh]);

  // Step 1A: Analyze Moodboard References
  const handleAnalyzeMoodboard = useCallback(async (promptOverride) => {
    const promptToSend = typeof promptOverride === 'string' ? promptOverride : baselinePrompt;

    if (files.length === 0) {
      onError?.('Please upload at least 1 moodboard reference file to begin.');
      return;
    }
    if (!promptToSend || !promptToSend.trim()) {
      onError?.('A starting creative prompt is required to analyze the moodboard.');
      return;
    }

    setIsAnalyzing(true);
    onError?.(null);

    try {
      const response = await analyzeMoodboard(
        files,
        promptToSend.trim(),
        lockedCategories,
        tagState,
        aspectRatio,
        visionModel
      );
      setMoodboardId(response.moodboard_id);

      const nextState = {
        master_prompt: response.master_prompt || null,
        categories: response.categories || {},
        locked_categories: lockedCategories,
      };
      setTagState(nextState);
      setBaselineTagSnapshot(JSON.parse(JSON.stringify(nextState)));
      setMasterPrompt(response.master_prompt || '');
      setPromptConflicts(response.conflicts || []);
    } catch (err) {
      onError?.(err.message || 'Failed to analyze moodboard references.');
    } finally {
      setIsAnalyzing(false);
    }
  }, [files, baselinePrompt, lockedCategories, tagState, aspectRatio, visionModel, onError]);

  // Step 1B: Generate 4 Baseline Image Candidates
  const handleGenerateBaselines = useCallback(async () => {
    if (!moodboardId && files.length === 0) {
      onError?.('Please upload and analyze moodboard references first.');
      return;
    }
    if (!masterPrompt || !masterPrompt.trim()) {
      onError?.('Master prompt cannot be empty. Please enter or re-sync the prompt.');
      return;
    }

    setIsGeneratingBaselines(true);
    onError?.(null);

    try {
      const payload = {
        moodboard_id: moodboardId || `mb_${Date.now()}`,
        master_prompt: masterPrompt.trim(),
        categories: tagState.categories,
        aspect_ratio: aspectRatio,
        prompt_override: masterPrompt.trim(),
        imagen_model: imagenModel,
        temperature: temperature,
      };

      const response = await generateBaselines(payload);

      if (response.baselines && response.baselines.length > 0) {
        setBaselines(response.baselines);
        setActiveBaseline(response.baselines[0]);
        onBaselineReady?.(response.baselines[0]);
      }
      await onHistoryRefresh?.();
    } catch (err) {
      onError?.(err.message || 'Failed to render 4 baseline image candidates.');
    } finally {
      setIsGeneratingBaselines(false);
    }
  }, [moodboardId, files.length, masterPrompt, tagState.categories, aspectRatio, imagenModel, temperature, onError, onBaselineReady, onHistoryRefresh]);

  // On-Demand Re-Sync: Visual Levers -> Master Generation Prompt
  const handleResyncPromptFromLevers = useCallback(async () => {
    setIsResyncingPrompt(true);
    onError?.(null);

    try {
      const response = await resyncPromptFromLevers({
        categories: tagState.categories,
        previous_master_prompt: masterPrompt,
        vision_model: visionModel,
      });

      if (response.master_prompt) {
        setMasterPrompt(response.master_prompt);
      }
      if (response.conflicts) {
        setPromptConflicts(response.conflicts);
      }

      setTagState((prev) => ({
        ...prev,
        master_prompt: response.master_prompt || prev.master_prompt,
      }));
    } catch (err) {
      onError?.(err.message || 'Failed to re-sync master prompt from visual levers.');
    } finally {
      setIsResyncingPrompt(false);
    }
  }, [tagState.categories, masterPrompt, visionModel, onError]);

  // On-Demand Re-Sync: Master Generation Prompt -> 9-Category Visual Levers
  const handleResyncLeversFromPrompt = useCallback(async () => {
    if (!masterPrompt.trim()) return;
    setIsResyncingLevers(true);
    onError?.(null);

    try {
      const response = await resyncLeversFromPrompt({
        master_prompt: masterPrompt,
        categories: tagState.categories,
        vision_model: visionModel,
      });

      if (response.conflicts) {
        setPromptConflicts(response.conflicts);
      }

      if (response.categories && Object.keys(response.categories).length > 0) {
        setTagState((prev) => ({
          ...prev,
          categories: response.categories,
        }));
      }
    } catch (err) {
      onError?.(err.message || 'Failed to extract visual levers from master prompt.');
    } finally {
      setIsResyncingLevers(false);
    }
  }, [masterPrompt, tagState.categories, visionModel, onError]);

  // On-Demand Scan for Contradictory Instructions & Conflicts
  const handleCheckConflicts = useCallback(async () => {
    if (!masterPrompt) return;
    setIsCheckingConflicts(true);
    try {
      const response = await checkPromptConflicts({
        master_prompt: masterPrompt,
        categories: tagState.categories,
        vision_model: visionModel,
      });
      setPromptConflicts(response.conflicts || []);
    } catch (err) {
      console.warn('Conflict scan failed:', err);
    } finally {
      setIsCheckingConflicts(false);
    }
  }, [masterPrompt, tagState.categories, visionModel]);

  const handleSelectBaseline = useCallback((baseline) => {
    setActiveBaseline(baseline);
    onBaselineReady?.(baseline);
  }, [onBaselineReady]);

  return {
    files,
    setFiles,
    baselinePrompt,
    setBaselinePrompt,
    aspectRatio,
    setAspectRatio,
    temperature,
    setTemperature,
    promptConflicts,
    setPromptConflicts,
    isCheckingConflicts,
    isAnalyzing,
    isGeneratingBaselines,
    isResyncingPrompt,
    isResyncingLevers,
    isDirectUploading,
    moodboardId,
    setMoodboardId,
    masterPrompt,
    setMasterPrompt,
    baselines,
    setBaselines,
    activeBaseline,
    setActiveBaseline,
    tagState,
    setTagState,
    lockedCategories,
    setLockedCategories,
    baselineTagSnapshot,
    setBaselineTagSnapshot,
    handleDirectPhotoUpload,
    handleAnalyzeMoodboard,
    handleGenerateBaselines,
    handleResyncPromptFromLevers,
    handleResyncLeversFromPrompt,
    handleCheckConflicts,
    handleSelectBaseline,
  };
}
