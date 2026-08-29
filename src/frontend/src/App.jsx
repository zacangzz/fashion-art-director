import React, { useState, useEffect } from 'react';
import {
  Sparkles,
  Layers,
  MessageSquare,
  Paintbrush,
  Download,
  History as HistoryIcon,
  AlertCircle,
  X,
  Activity,
  ExternalLink,
  Eye,
  Cpu,
} from 'lucide-react';

import MoodboardUploader from './components/MoodboardUploader';
import PromptReviewSection from './components/PromptReviewSection';
import BaselineSelector, { getBaseResolution, getMasterResolution } from './components/BaselineSelector';
import RefinementChat from './components/RefinementChat';
import WardrobePanel from './components/WardrobePanel';
import CanvasStudio from './components/CanvasStudio';
import CanvasViewport from './components/CanvasViewport';
import ExportStudio from './components/ExportStudio';
import HistoryDrawer from './components/HistoryDrawer';
import ComparisonModal from './components/ComparisonModal';

import { DEFAULT_TAG_STATE } from './utils/defaultTags';
import { compileModularPrompt } from './utils/promptCompiler';
import {
  analyzeMoodboard,
  generateBaselines,
  resyncMasterPrompt,
  checkPromptConflicts,
  analyzeAndGenerateBaselines,
  uploadDirectPhoto,
  refineGeneration,
  composeWardrobe,
  fetchConversation,
  exportBundle,
  fetchHistory,
  restoreGeneration,
  fetchModelConfig,
} from './services/apiClient';

export default function App() {
  // 4-Step Sequential Workflow: 1: Art Direction, 2: Refinement, 3: Canvas, 4: Export
  const [currentStep, setCurrentStep] = useState(1);

  // Model Selection state
  const [modelConfig, setModelConfig] = useState({
    available_vision_models: ['gemini-3.5-flash-lite', 'gemini-3.7-flash'],
    available_imagen_models: ['gemini-3.1-flash-lite-image', 'gemini-3.1-flash-image', 'gemini-3-pro-image'],
    default_vision_model: 'gemini-3.5-flash-lite',
    default_imagen_model: 'gemini-3.1-flash-image',
    inpaint_model: 'gemini-3-pro-image',
  });
  const [visionModel, setVisionModel] = useState(() => localStorage.getItem('studio_vision_model') || 'gemini-3.5-flash-lite');
  const [imagenModel, setImagenModel] = useState(() => localStorage.getItem('studio_imagen_model') || 'gemini-3.1-flash-image');

  // Step 1: Ingest & Baselines state
  const [files, setFiles] = useState([]);
  const [baselinePrompt, setBaselinePrompt] = useState('');
  const [aspectRatio, setAspectRatio] = useState('1.8:1');
  const [temperature, setTemperature] = useState(1.0);
  const [promptConflicts, setPromptConflicts] = useState([]);
  const [isCheckingConflicts, setIsCheckingConflicts] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isGeneratingBaselines, setIsGeneratingBaselines] = useState(false);
  const [isResyncingPrompt, setIsResyncingPrompt] = useState(false);
  const [moodboardId, setMoodboardId] = useState(null);
  const [masterPrompt, setMasterPrompt] = useState('');
  const [sceneNarrative, setSceneNarrative] = useState('');
  const [baselines, setBaselines] = useState([]);
  const [activeBaseline, setActiveBaseline] = useState(null);

  // TagState for initial extraction & baseline generation
  const [tagState, setTagState] = useState(DEFAULT_TAG_STATE);
  const [lockedCategories, setLockedCategories] = useState([]);
  const [baselineTagSnapshot, setBaselineTagSnapshot] = useState(null);
  const [useImageReference, setUseImageReference] = useState(true);

  // Step 2: Conversation-based Refinement state
  const [conversationId, setConversationId] = useState(null);
  const [conversationMessages, setConversationMessages] = useState([]);

  // Wardrobe Composition Studio state
  const [isWardrobeOpen, setIsWardrobeOpen] = useState(false);
  const [wardrobeAssignments, setWardrobeAssignments] = useState([]);
  const [isComposingWardrobe, setIsComposingWardrobe] = useState(false);

  // Generation & Viewport state

  const [isGenerating, setIsGenerating] = useState(false);
  const [isInpainting, setIsInpainting] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [generationResult, setGenerationResult] = useState(null);
  const [previousGenerationResult, setPreviousGenerationResult] = useState(null);
  const [activeSeed, setActiveSeed] = useState(4289102);
  const [seedMode, setSeedMode] = useState('locked');

  // History & Lineage state
  const [history, setHistory] = useState([]);
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [selectedForCompare, setSelectedForCompare] = useState([]);
  const [isCompareOpen, setIsCompareOpen] = useState(false);

  // Error alert state
  const [errorMessage, setErrorMessage] = useState(null);
  const [isDirectUploading, setIsDirectUploading] = useState(false);

  // Load history and model configuration on mount
  useEffect(() => {
    loadHistoryList();
    loadModelConfig();
  }, []);

  const loadModelConfig = async () => {
    try {
      const cfg = await fetchModelConfig();
      if (cfg) {
        setModelConfig(cfg);
        const storedVision = localStorage.getItem('studio_vision_model');
        const storedImagen = localStorage.getItem('studio_imagen_model');
        if (!storedVision && cfg.default_vision_model) {
          setVisionModel(cfg.default_vision_model);
        }
        if (!storedImagen && cfg.default_imagen_model) {
          setImagenModel(cfg.default_imagen_model);
        }
      }
    } catch (err) {
      console.warn('Failed to load dynamic model configuration:', err);
    }
  };

  const handleVisionModelChange = (model) => {
    setVisionModel(model);
    localStorage.setItem('studio_vision_model', model);
  };

  const handleImagenModelChange = (model) => {
    setImagenModel(model);
    localStorage.setItem('studio_imagen_model', model);
  };

  const loadHistoryList = async () => {
    try {
      const res = await fetchHistory();
      if (res && res.generations) {
        setHistory(res.generations);
      }
    } catch (err) {
      console.error('Failed to load history:', err);
    }
  };

  // Step 1: Skip Art Direction via Direct Photo Ingestion
  const handleDirectPhotoUpload = async (file, detectedRatio) => {
    if (!file) return;
    setIsDirectUploading(true);
    setErrorMessage(null);

    try {
      const response = await uploadDirectPhoto(file, detectedRatio || aspectRatio);

      const baselineObj = {
        id: response.generation_id,
        seed: response.seed,
        image_url: response.image_url,
        created_at: response.created_at,
        aspect_ratio: response.aspect_ratio,
        resolution: response.resolution,
        compiled_prompt: response.compiled_prompt,
      };

      setActiveBaseline(baselineObj);
      setActiveSeed(response.seed);
      if (response.aspect_ratio) {
        setAspectRatio(response.aspect_ratio);
      }
      setPreviousGenerationResult(null);

      const effRatio = response.aspect_ratio || aspectRatio;
      const initialGen = {
        generation_id: response.generation_id,
        master_image_url: response.image_url,
        seed: response.seed,
        compiled_prompt: response.compiled_prompt,
        aspect_ratio: effRatio,
        resolution: response.resolution || getBaseResolution(effRatio),
      };
      setGenerationResult(initialGen);

      // Initialize conversation messages with uploaded image baseline
      const baseMsg = {
        role: 'baseline',
        prompt: response.compiled_prompt,
        generation_id: response.generation_id,
        image_url: response.image_url,
        seed: response.seed,
        created_at: response.created_at || new Date().toISOString(),
      };
      setConversationMessages([baseMsg]);
      setConversationId(`conv_${response.generation_id}`);

      await loadHistoryList();
      setCurrentStep(2);
    } catch (err) {
      setErrorMessage(err.message || 'Direct photo upload failed.');
    } finally {
      setIsDirectUploading(false);
    }
  };

  // Step 1A: Analyze Moodboard References & Synthesize Master Prompt + Visual Levers
  const handleAnalyzeMoodboard = async (promptOverride) => {
    const promptToSend = typeof promptOverride === 'string' ? promptOverride : baselinePrompt;

    if (files.length === 0) {
      setErrorMessage('Please upload at least 1 moodboard reference file to begin.');
      return;
    }
    if (!promptToSend || !promptToSend.trim()) {
      setErrorMessage('A starting creative prompt is required to analyze the moodboard.');
      return;
    }

    setIsAnalyzing(true);
    setErrorMessage(null);

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
        narrative: response.narrative || promptToSend || tagState.narrative,
        categories: response.categories || {},
        locked_categories: lockedCategories,
      };
      setTagState(nextState);
      setBaselineTagSnapshot(JSON.parse(JSON.stringify(nextState)));
      setMasterPrompt(response.master_prompt || '');
      setSceneNarrative(response.narrative || promptToSend || '');
      setPromptConflicts(response.conflicts || []);
    } catch (err) {
      setErrorMessage(err.message || 'Failed to analyze moodboard references.');
    } finally {
      setIsAnalyzing(false);
    }
  };

  // Step 1B: Generate 4 Baseline Image Candidates from Customized Master Prompt
  const handleGenerateBaselines = async () => {
    if (!moodboardId && files.length === 0) {
      setErrorMessage('Please upload and analyze moodboard references first.');
      return;
    }
    if (!masterPrompt || !masterPrompt.trim()) {
      setErrorMessage('Master prompt cannot be empty. Please enter or re-sync the prompt.');
      return;
    }

    setIsGeneratingBaselines(true);
    setErrorMessage(null);

    try {
      const payload = {
        moodboard_id: moodboardId || `mb_${Date.now()}`,
        master_prompt: masterPrompt.trim(),
        narrative: sceneNarrative.trim(),
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
        setActiveSeed(response.baselines[0].seed);
      }
      await loadHistoryList();
    } catch (err) {
      setErrorMessage(err.message || 'Failed to render 4 baseline image candidates.');
    } finally {
      setIsGeneratingBaselines(false);
    }
  };

  // On-Demand AI Master Prompt Re-Sync from Edited Visual Levers
  const handleResyncMasterPrompt = async () => {
    setIsResyncingPrompt(true);
    setErrorMessage(null);

    try {
      const response = await resyncMasterPrompt({
        narrative: sceneNarrative,
        categories: tagState.categories,
        previous_master_prompt: masterPrompt,
        vision_model: visionModel,
      });

      if (response.master_prompt) {
        setMasterPrompt(response.master_prompt);
      }
      if (response.narrative) {
        setSceneNarrative(response.narrative);
      }
      if (response.conflicts) {
        setPromptConflicts(response.conflicts);
      }

      setTagState((prev) => ({
        ...prev,
        master_prompt: response.master_prompt || prev.master_prompt,
        narrative: response.narrative || prev.narrative,
      }));
    } catch (err) {
      setErrorMessage(err.message || 'Failed to re-sync master prompt with AI.');
    } finally {
      setIsResyncingPrompt(false);
    }
  };

  // On-Demand Scan for Contradictory Instructions & Conflicts
  const handleCheckConflicts = async () => {
    if (!masterPrompt && !sceneNarrative) return;
    setIsCheckingConflicts(true);
    try {
      const response = await checkPromptConflicts({
        master_prompt: masterPrompt,
        narrative: sceneNarrative,
        categories: tagState.categories,
        vision_model: visionModel,
      });
      setPromptConflicts(response.conflicts || []);
    } catch (err) {
      console.warn('Conflict scan failed:', err);
    } finally {
      setIsCheckingConflicts(false);
    }
  };

  // Select Baseline
  const handleSelectBaseline = (baseline) => {
    setActiveBaseline(baseline);
    setActiveSeed(baseline.seed);
  };

  // Advance from Step 1 to Step 2 (Refinement)
  const handleProceedToStudio = (baseline) => {
    if (baseline) {
      setActiveBaseline(baseline);
      setActiveSeed(baseline.seed);
      setPreviousGenerationResult(null);

      const compiled = baseline.compiled_prompt || masterPrompt || compileModularPrompt(tagState.narrative, tagState.categories);
      const effRatio = baseline.aspect_ratio || aspectRatio;
      const initialGen = {
        generation_id: baseline.id,
        master_image_url: baseline.image_url,
        seed: baseline.seed,
        compiled_prompt: compiled,
        aspect_ratio: effRatio,
        resolution: baseline.resolution || getBaseResolution(effRatio),
      };
      setGenerationResult(initialGen);

      // Initialize conversation messages with baseline
      const baseMsg = {
        role: 'baseline',
        prompt: compiled,
        generation_id: baseline.id,
        image_url: baseline.image_url,
        seed: baseline.seed,
        created_at: baseline.created_at || new Date().toISOString(),
      };
      setConversationMessages([baseMsg]);
      setConversationId(`conv_${baseline.id}`);
    }
    setCurrentStep(2);
  };

  // Step 2: Handle Refinement Prompt from RefinementChat
  const handleSendRefinement = async (promptText) => {
    if (!promptText || !promptText.trim()) return;

    setIsGenerating(true);
    setErrorMessage(null);

    const parentId = generationResult?.generation_id || activeBaseline?.id;
    const effSeed = seedMode === 'locked' ? activeSeed : Math.floor(Math.random() * 9000000) + 1000000;

    try {
      const payload = {
        parent_id: parentId,
        prompt: promptText.trim(),
        seed: effSeed,
        seed_mode: seedMode,
        aspect_ratio: aspectRatio,
        conversation_id: conversationId,
        imagen_model: imagenModel,
      };

      const result = await refineGeneration(payload);

      if (generationResult) {
        setPreviousGenerationResult(generationResult);
      }

      const effRatio = result.aspect_ratio || aspectRatio;
      const nextGen = {
        generation_id: result.generation_id,
        master_image_url: result.image_url,
        seed: result.seed,
        compiled_prompt: result.compiled_prompt,
        aspect_ratio: effRatio,
        resolution: result.resolution || getBaseResolution(effRatio),
      };
      setGenerationResult(nextGen);
      setActiveSeed(result.seed);

      if (result.conversation_id && !conversationId) {
        setConversationId(result.conversation_id);
      }

      // Append new message to conversation
      const newMsg = {
        role: 'user',
        prompt: promptText.trim(),
        generation_id: result.generation_id,
        image_url: result.image_url,
        seed: result.seed,
        created_at: result.created_at || new Date().toISOString(),
      };
      setConversationMessages((prev) => [...prev, newMsg]);

      await loadHistoryList();
    } catch (err) {
      setErrorMessage(err.message || 'Refinement generation failed.');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleSelectMessage = (msg) => {
    if (!msg || !msg.generation_id) return;
    if (generationResult && generationResult.generation_id !== msg.generation_id) {
      setPreviousGenerationResult(generationResult);
    }
    const effRatio = msg.aspect_ratio || aspectRatio;
    setGenerationResult({
      generation_id: msg.generation_id,
      master_image_url: msg.image_url,
      seed: msg.seed,
      compiled_prompt: msg.prompt,
      aspect_ratio: effRatio,
      resolution: msg.resolution || getBaseResolution(effRatio),
    });
    setActiveSeed(msg.seed);
  };

  // Wardrobe Composition Handlers
  const handleAddWardrobeAssignment = (garmentItem, dropPosition) => {
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
  };

  const handleUpdateWardrobePosition = (pinNumber, newPosition) => {
    setWardrobeAssignments((prev) =>
      prev.map((a) => (a.pin_number === pinNumber ? { ...a, drop_position: newPosition } : a))
    );
  };

  const handleRemoveWardrobeAssignment = (pinNumber) => {
    setWardrobeAssignments((prev) => {
      const filtered = prev.filter((a) => a.pin_number !== pinNumber);
      return filtered.map((a, idx) => ({ ...a, pin_number: idx + 1 }));
    });
  };

  const handleClearWardrobeAssignments = () => {
    setWardrobeAssignments([]);
  };

  const handleComposeWardrobe = async (customInstruction = '') => {
    if (wardrobeAssignments.length === 0) return;

    setIsComposingWardrobe(true);
    setIsGenerating(true);
    setErrorMessage(null);

    const parentId = generationResult?.generation_id || activeBaseline?.id;
    const effSeed = seedMode === 'locked' ? activeSeed : Math.floor(Math.random() * 9000000) + 1000000;

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
        aspect_ratio: aspectRatio,
        conversation_id: conversationId,
        custom_instruction: customInstruction,
        imagen_model: imagenModel,
        vision_model: visionModel,
      };

      const result = await composeWardrobe(payload);

      if (generationResult) {
        setPreviousGenerationResult(generationResult);
      }

      const effRatio = result.aspect_ratio || aspectRatio;
      const nextGen = {
        generation_id: result.generation_id,
        master_image_url: result.image_url,
        seed: result.seed,
        compiled_prompt: result.compiled_prompt,
        aspect_ratio: effRatio,
        resolution: result.resolution || getBaseResolution(effRatio),
      };
      setGenerationResult(nextGen);
      setActiveSeed(result.seed);

      if (result.conversation_id && !conversationId) {
        setConversationId(result.conversation_id);
      }

      // Append new message to conversation thread
      const newMsg = {
        role: 'user',
        prompt: `Wardrobe Swap (${wardrobeAssignments.length} item${wardrobeAssignments.length !== 1 ? 's' : ''}): ` + wardrobeAssignments.map((a) => `#${a.pin_number} ${a.item_label}`).join(', '),
        generation_id: result.generation_id,
        image_url: result.image_url,
        seed: result.seed,
        created_at: result.created_at || new Date().toISOString(),
      };
      setConversationMessages((prev) => [...prev, newMsg]);

      // Reset assignments
      setWardrobeAssignments([]);
      await loadHistoryList();
    } catch (err) {
      setErrorMessage(err.message || 'Wardrobe composition failed.');
    } finally {
      setIsComposingWardrobe(false);
      setIsGenerating(false);
    }
  };

  // Step 3: Canvas Studio Inpainting Completed
  const handleInpaintComplete = async (result) => {
    if (!result) return;
    if (generationResult) {
      setPreviousGenerationResult(generationResult);
    }
    const effRatio = result.aspect_ratio || aspectRatio;
    const nextGen = {
      generation_id: result.generation_id,
      master_image_url: result.image_url,
      seed: result.seed,
      compiled_prompt: result.compiled_prompt,
      aspect_ratio: effRatio,
      resolution: result.resolution || getBaseResolution(effRatio),
    };
    setGenerationResult(nextGen);

    // Also add to conversation messages
    const inpaintMsg = {
      role: 'user',
      prompt: `[Inpaint Edit] ${result.compiled_prompt}`,
      generation_id: result.generation_id,
      image_url: result.image_url,
      seed: result.seed,
      created_at: result.created_at || new Date().toISOString(),
    };
    setConversationMessages((prev) => [...prev, inpaintMsg]);

    await loadHistoryList();
  };

  // Step 4: Export 5-Preset ZIP Bundle
  const handleExportBundle = async (genId) => {
    const targetId = genId || generationResult?.generation_id || activeBaseline?.id;
    if (!targetId) return;

    setIsExporting(true);
    setErrorMessage(null);
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
      setErrorMessage(err.message || 'Failed to download export bundle.');
    } finally {
      setIsExporting(false);
    }
  };

  // Restore state from History Lineage Drawer
  const handleRestoreState = async (record) => {
    setActiveSeed(record.seed);

    // Reconstruct full ancestor lineage chain from history
    // Trace back through parent_id pointers to root baseline
    const lineageChain = [];
    let curr = record;
    const visited = new Set();
    while (curr && !visited.has(curr.id)) {
      visited.add(curr.id);
      lineageChain.unshift(curr);
      if (curr.is_baseline || !curr.parent_id) break;
      curr = history.find((h) => h.id === curr.parent_id);
    }

    const rootBaseline = lineageChain[0] || (record.is_baseline ? record : null);
    if (rootBaseline) {
      setActiveBaseline({
        id: rootBaseline.id,
        image_url: rootBaseline.master_image_url || rootBaseline.image_url,
        seed: rootBaseline.seed,
        compiled_prompt: rootBaseline.compiled_prompt || rootBaseline.prompt,
      });
    }

    const targetRatio = record.aspect_ratio || aspectRatio;
    const masterRes = getMasterResolution(targetRatio);
    if (parent) {
      const parentRatio = parent.aspect_ratio || targetRatio;
      const parentMasterRes = getMasterResolution(parentRatio);
      setPreviousGenerationResult({
        generation_id: parent.id,
        master_image_url: parent.master_image_url || parent.image_url,
        seed: parent.seed,
        compiled_prompt: parent.compiled_prompt || parent.prompt,
        aspect_ratio: parentRatio,
        resolution: { width: parent.resolution_width || parentMasterRes.width, height: parent.resolution_height || parentMasterRes.height },
      });
    } else {
      setPreviousGenerationResult(null);
    }

    const restoredGen = {
      generation_id: record.id,
      master_image_url: record.master_image_url || record.image_url,
      seed: record.seed,
      compiled_prompt: record.compiled_prompt || record.prompt,
      aspect_ratio: targetRatio,
      resolution: { width: record.resolution_width || masterRes.width, height: record.resolution_height || masterRes.height },
      schema_json: record.schema_json,
    };
    setGenerationResult(restoredGen);

    // Build or fetch conversation messages
    let loadedMessages = null;
    const convId = record.conversation_id || (record.schema_json && record.schema_json.conversation_id);
    if (convId) {
      try {
        const convData = await fetchConversation(convId);
        if (convData && convData.messages && convData.messages.length > 0) {
          setConversationId(convId);
          loadedMessages = convData.messages;
        }
      } catch (e) {
        console.warn('Could not fetch full conversation for restored item:', e);
      }
    }

    if (loadedMessages && loadedMessages.length > 0) {
      setConversationMessages(loadedMessages);
    } else {
      // Reconstruct messages from ancestor lineage chain
      const reconstructed = lineageChain.map((item, idx) => ({
        role: idx === 0 && item.is_baseline ? 'baseline' : 'user',
        prompt: item.compiled_prompt || item.prompt || (item.is_baseline ? 'Initial Baseline' : 'Iterative Refinement'),
        generation_id: item.id,
        image_url: item.master_image_url || item.image_url,
        seed: item.seed,
        created_at: item.created_at || new Date().toISOString(),
        is_inpaint: item.id?.startsWith('gen_inpaint_') || Boolean(item.inpaint_metadata || item.schema_json?.inpaint_metadata),
        is_wardrobe: Boolean(item.schema_json?.wardrobe_composition),
      }));
      setConversationMessages(reconstructed);
      setConversationId(convId || `conv_${record.id}`);
    }

    setIsHistoryOpen(false);
    if (currentStep === 1 || currentStep === 4) {
      setCurrentStep(2);
    }
  };

  // Compare toggles
  const handleToggleCompare = (id) => {
    setSelectedForCompare((prev) => {
      if (prev.includes(id)) {
        return prev.filter((item) => item !== id);
      }
      if (prev.length >= 2) return prev;
      return [...prev, id];
    });
  };

  const compareVersionA = history.find((h) => h.id === selectedForCompare[0]);
  const compareVersionB = history.find((h) => h.id === selectedForCompare[1]);

  const hasActiveImage = Boolean(generationResult?.master_image_url || activeBaseline?.image_url);

  return (
    <div className="app-container">
      {/* Top Header */}
      <header className="header">
        <div className="header-brand">
          <div className="header-logo">
            <Sparkles size={20} />
          </div>
          <span className="header-title">Image Gen Pipeline Studio</span>
        </div>

        {/* 4-Step Sequential Workflow Navigator */}
        <div className="step-nav-bar">
          <button
            type="button"
            className={`step-nav-btn ${currentStep === 1 ? 'active' : ''}`}
            onClick={() => setCurrentStep(1)}
          >
            <span className="step-num">1</span>
            <span>Art Direction</span>
          </button>

          <button
            type="button"
            className={`step-nav-btn ${currentStep === 2 ? 'active' : ''}`}
            onClick={() => setCurrentStep(2)}
            disabled={!hasActiveImage}
          >
            <span className="step-num">2</span>
            <span>Refinement</span>
          </button>

          <button
            type="button"
            className={`step-nav-btn ${currentStep === 3 ? 'active' : ''}`}
            onClick={() => setCurrentStep(3)}
            disabled={!hasActiveImage}
          >
            <span className="step-num">3</span>
            <span>Canvas</span>
          </button>

          <button
            type="button"
            className={`step-nav-btn ${currentStep === 4 ? 'active' : ''}`}
            onClick={() => setCurrentStep(4)}
            disabled={!hasActiveImage}
          >
            <span className="step-num">4</span>
            <span>Export</span>
          </button>
        </div>

        {/* Header Actions & Model Selectors */}
        <div className="header-actions">
          <div className="model-selectors-container">
            <div className="model-selector-chip" title="Vision Model for Analysis, Directing & Pin Grounding">
              <Eye size={12} className="text-cyan-400 shrink-0" />
              <span className="model-selector-chip-label">Vision</span>
              <select
                className="model-select-input"
                value={visionModel}
                onChange={(e) => handleVisionModelChange(e.target.value)}
              >
                {modelConfig.available_vision_models.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            </div>

            <div className="model-selector-chip" title="Image Model for Baselines, Fine-Tuning & Refinement">
              <Cpu size={12} className="text-amber-400 shrink-0" />
              <span className="model-selector-chip-label">Imagen</span>
              <select
                className="model-select-input"
                value={imagenModel}
                onChange={(e) => handleImagenModelChange(e.target.value)}
              >
                {modelConfig.available_imagen_models.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <a
            href="/telemetry"
            target="_blank"
            rel="noopener noreferrer"
            className="btn-secondary btn-sm"
            title="Open Studio Observability, Telemetry & Database in a separate tab"
          >
            <Activity size={14} className="text-indigo-400" />
            <span>Observability & Logs</span>
            <ExternalLink size={11} className="opacity-60" />
          </a>

          <button
            type="button"
            className="btn-secondary btn-sm"
            onClick={() => setIsHistoryOpen(true)}
          >
            <HistoryIcon size={14} />
            <span>Lineage History ({history.length})</span>
          </button>
        </div>
      </header>

      {/* Error Banner */}
      {errorMessage && (
        <div className="error-banner">
          <div className="error-banner-content">
            <AlertCircle size={16} />
            <span>{errorMessage}</span>
          </div>
          <button
            type="button"
            className="error-banner-close"
            onClick={() => setErrorMessage(null)}
          >
            <X size={16} />
          </button>
        </div>
      )}

      {/* Main Studio Viewport */}
      <main className="studio-main-container">
        {currentStep === 1 && (
          /* Step 1: Moodboard Upload & 2-Stage Analysis + 4-Baseline Selector */
          <div className="step-1-layout">
            <MoodboardUploader
              files={files}
              onFilesChange={setFiles}
              prompt={baselinePrompt}
              onPromptChange={setBaselinePrompt}
              onAnalyze={handleAnalyzeMoodboard}
              isAnalyzing={isAnalyzing}
              aspectRatio={aspectRatio}
              onAspectRatioChange={setAspectRatio}
              onDirectPhotoUpload={handleDirectPhotoUpload}
              isDirectUploading={isDirectUploading}
            />

            <div className="step-1-right-column">
              {(moodboardId || masterPrompt || (tagState?.categories && Object.keys(tagState.categories).length > 0)) ? (
                <>
                  <PromptReviewSection
                    tagState={tagState}
                    onUpdateTagState={setTagState}
                    masterPrompt={masterPrompt}
                    onMasterPromptChange={setMasterPrompt}
                    narrative={sceneNarrative}
                    onNarrativeChange={setSceneNarrative}
                    aspectRatio={aspectRatio}
                    temperature={temperature}
                    onTemperatureChange={setTemperature}
                    conflicts={promptConflicts}
                    isCheckingConflicts={isCheckingConflicts}
                    onCheckConflicts={handleCheckConflicts}
                    isResyncing={isResyncingPrompt}
                    onResyncPrompt={handleResyncMasterPrompt}
                    isGeneratingBaselines={isGeneratingBaselines}
                    onGenerateBaselines={handleGenerateBaselines}
                    hasBaselines={baselines.length > 0}
                  />

                  {baselines.length > 0 ? (
                    <BaselineSelector
                      baselines={baselines}
                      selectedBaselineId={activeBaseline?.id}
                      onSelectBaseline={handleSelectBaseline}
                      onProceedToStudio={handleProceedToStudio}
                      tagState={tagState}
                      aspectRatio={aspectRatio}
                    />
                  ) : (
                    <div className="baseline-selector-container">
                      <div className="viewport-empty-placeholder" style={{ padding: '40px 20px' }}>
                        <Sparkles size={36} className="placeholder-icon text-accent" />
                        <div className="placeholder-title">Visual Direction & Levers Extracted</div>
                        <div className="placeholder-subtitle">
                          Review and customize your Master Prompt or visual levers above, then click <strong>"Generate 4 Baseline Candidates"</strong> to render candidate seeds across Google GenAI.
                        </div>
                      </div>
                    </div>
                  )}
                </>
              ) : (
                <div className="baseline-selector-container">
                  <div className="viewport-empty-placeholder" style={{ padding: '60px 20px' }}>
                    <Layers size={48} className="placeholder-icon" />
                    <div className="placeholder-title">Step 1: Moodboard Analysis & Foundation Setup</div>
                    <div className="placeholder-subtitle">
                      Upload 1–5 moodboard reference images or PDFs on the left, enter your starting scene prompt, and click <strong>"Analyze Moodboard"</strong> to synthesize your Director's Master Prompt and 9-category visual levers.
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {currentStep === 2 && (
          /* Step 2: Refinement Chat + Master Viewport + Optional Wardrobe Studio Panel */
          <div className={`workspace-grid ${isWardrobeOpen ? 'with-wardrobe-panel' : ''}`}>
            <div className="workspace-left-column">
              <RefinementChat
                conversationMessages={conversationMessages}
                onSendRefinement={handleSendRefinement}
                isGenerating={isGenerating}
                activeSeed={activeSeed}
                seedMode={seedMode}
                onSeedModeChange={setSeedMode}
                onSeedChange={setActiveSeed}
                activeGenerationId={generationResult?.generation_id}
                onSelectMessage={handleSelectMessage}
                onToggleWardrobe={() => setIsWardrobeOpen(!isWardrobeOpen)}
                isWardrobeOpen={isWardrobeOpen}
                assignmentCount={wardrobeAssignments.length}
              />
            </div>

            <div className="workspace-right-column">
              <div className="workspace-viewport-wrapper">
                <CanvasViewport
                  imageUrl={generationResult?.master_image_url || activeBaseline?.image_url || null}
                  beforeImageUrl={previousGenerationResult?.master_image_url || activeBaseline?.image_url || null}
                  baselineImageUrl={activeBaseline?.image_url || null}
                  beforeLabel={
                    previousGenerationResult && previousGenerationResult.generation_id !== activeBaseline?.id
                      ? 'Previous Iteration'
                      : 'Baseline'
                  }
                  afterLabel="Refined Output"
                  isGenerating={isGenerating}
                  isExporting={isExporting}
                  generationResult={generationResult}
                  previousGenerationResult={previousGenerationResult}
                  activeSeed={activeSeed}
                  seedMode={seedMode}
                  onExportBundle={handleExportBundle}
                  onOpenHistory={() => setIsHistoryOpen(true)}
                  canGenerate={false}
                  mode="refinement"
                  wardrobeAssignments={wardrobeAssignments}
                  onDropGarment={handleAddWardrobeAssignment}
                  onRemovePin={handleRemoveWardrobeAssignment}
                  onUpdatePinPosition={handleUpdateWardrobePosition}
                  isWardrobeMode={isWardrobeOpen}
                />
              </div>
            </div>

            {isWardrobeOpen && (
              <div className="workspace-wardrobe-column">
                <WardrobePanel
                  isOpen={isWardrobeOpen}
                  onClose={() => setIsWardrobeOpen(false)}
                  assignments={wardrobeAssignments}
                  onAddAssignment={handleAddWardrobeAssignment}
                  onRemoveAssignment={handleRemoveWardrobeAssignment}
                  onClearAssignments={handleClearWardrobeAssignments}
                  onCompose={handleComposeWardrobe}
                  isComposing={isComposingWardrobe}
                  activeGenerationId={generationResult?.generation_id || activeBaseline?.id}
                  visionModel={visionModel}
                />
              </div>
            )}
          </div>
        )}

        {currentStep === 3 && (
          /* Step 3: Canvas Studio Inpainting + Master Viewport */
          <div className="workspace-grid inpaint-workspace-grid">
            <div className="workspace-left-column">
              <CanvasStudio
                imageUrl={generationResult?.master_image_url || activeBaseline?.image_url || null}
                generationId={generationResult?.generation_id || activeBaseline?.id}
                activeSeed={activeSeed}
                onEditComplete={handleInpaintComplete}
                onSwitchToGraph={() => setCurrentStep(2)}
                onOpenHistory={() => setIsHistoryOpen(true)}
                isInpainting={isInpainting}
                setIsInpainting={setIsInpainting}
              />
            </div>

            <div className="workspace-right-column">
              <div className="workspace-viewport-wrapper">
                <CanvasViewport
                  imageUrl={generationResult?.master_image_url || activeBaseline?.image_url || null}
                  beforeImageUrl={previousGenerationResult?.master_image_url || activeBaseline?.image_url || null}
                  baselineImageUrl={activeBaseline?.image_url || null}
                  beforeLabel={
                    previousGenerationResult && previousGenerationResult.generation_id !== activeBaseline?.id
                      ? 'Before Inpaint'
                      : 'Baseline'
                  }
                  afterLabel="Inpainted Output"
                  isGenerating={isInpainting}
                  isInpaintMode={true}
                  isExporting={isExporting}
                  generationResult={generationResult}
                  previousGenerationResult={previousGenerationResult}
                  activeSeed={activeSeed}
                  seedMode={seedMode}
                  onExportBundle={handleExportBundle}
                  onOpenHistory={() => setIsHistoryOpen(true)}
                  canGenerate={false}
                  mode="canvas"
                />
              </div>
            </div>
          </div>
        )}

        {currentStep === 4 && (
          /* Step 4: Dedicated Export Page */
          <ExportStudio
            generationResult={generationResult}
            activeBaseline={activeBaseline}
            globalAspectRatio={aspectRatio}
            history={history}
            onExportMasterPrepared={(result) => {
              setGenerationResult(result);
              loadHistoryList();
            }}
          />
        )}

      </main>

      {/* Slide-out History Lineage Drawer */}
      <HistoryDrawer
        isOpen={isHistoryOpen}
        onClose={() => setIsHistoryOpen(false)}
        history={history}
        activeGenerationId={generationResult?.generation_id}
        onRestoreGeneration={handleRestoreState}
        selectedForCompare={selectedForCompare}
        onToggleCompare={handleToggleCompare}
        onOpenCompareModal={() => setIsCompareOpen(true)}
      />

      {/* Side-by-Side Split-Slider Comparison Modal */}
      {isCompareOpen && compareVersionA && compareVersionB && (
        <ComparisonModal
          isOpen={isCompareOpen}
          onClose={() => setIsCompareOpen(false)}
          versionA={compareVersionA}
          versionB={compareVersionB}
        />
      )}
    </div>
  );
}
