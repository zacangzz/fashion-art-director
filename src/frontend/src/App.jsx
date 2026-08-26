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
} from 'lucide-react';

import MoodboardUploader from './components/MoodboardUploader';
import BaselineSelector from './components/BaselineSelector';
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
  analyzeAndGenerateBaselines,
  refineGeneration,
  composeWardrobe,
  fetchConversation,
  exportBundle,
  fetchHistory,
  restoreGeneration,
} from './services/apiClient';

export default function App() {
  // 4-Step Sequential Workflow: 1: Art Direction, 2: Refinement, 3: Canvas, 4: Export
  const [currentStep, setCurrentStep] = useState(1);

  // Step 1: Ingest & Baselines state
  const [files, setFiles] = useState([]);
  const [baselinePrompt, setBaselinePrompt] = useState('');
  const [aspectRatio, setAspectRatio] = useState('1.8:1');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [moodboardId, setMoodboardId] = useState(null);
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

  // Load history on mount
  useEffect(() => {
    loadHistoryList();
  }, []);

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

  // Step 1: Analyze Moodboard & Generate 4 Baselines
  const handleAnalyzeAndGenerateBaselines = async (promptOverride) => {
    const promptToSend = typeof promptOverride === 'string' ? promptOverride : baselinePrompt;

    if (files.length === 0) {
      setErrorMessage('Please upload at least 1 moodboard reference file to begin.');
      return;
    }
    if (!promptToSend || !promptToSend.trim()) {
      setErrorMessage('A starting creative prompt is required to analyze the moodboard and generate baselines.');
      return;
    }

    setIsAnalyzing(true);
    setErrorMessage(null);

    try {
      const response = await analyzeAndGenerateBaselines(
        files,
        promptToSend.trim(),
        lockedCategories,
        tagState,
        aspectRatio
      );
      setMoodboardId(response.moodboard_id);

      if (response.categories && Object.keys(response.categories).length > 0) {
        const nextState = {
          master_prompt: response.master_prompt || null,
          narrative: response.narrative || promptToSend || tagState.narrative,
          categories: response.categories,
          locked_categories: lockedCategories,
        };
        setTagState(nextState);
        setBaselineTagSnapshot(JSON.parse(JSON.stringify(nextState)));
      }

      if (response.baselines && response.baselines.length > 0) {
        setBaselines(response.baselines);
        setActiveBaseline(response.baselines[0]);
        setActiveSeed(response.baselines[0].seed);
      }
      await loadHistoryList();
    } catch (err) {
      setErrorMessage(err.message || 'Failed to analyze moodboard and render baselines.');
    } finally {
      setIsAnalyzing(false);
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

      const compiled = baseline.compiled_prompt || compileModularPrompt(tagState.narrative, tagState.categories);
      const initialGen = {
        generation_id: baseline.id,
        master_image_url: baseline.image_url,
        seed: baseline.seed,
        compiled_prompt: compiled,
        resolution: baseline.resolution || { width: 1080, height: 1620 },
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
      };

      const result = await refineGeneration(payload);

      if (generationResult) {
        setPreviousGenerationResult(generationResult);
      }

      const nextGen = {
        generation_id: result.generation_id,
        master_image_url: result.image_url,
        seed: result.seed,
        compiled_prompt: result.compiled_prompt,
        resolution: result.resolution || { width: 1080, height: 1620 },
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

  // Handle selecting a past message from the RefinementChat thread
  const handleSelectMessage = (msg) => {
    if (!msg || !msg.generation_id) return;
    if (generationResult && generationResult.generation_id !== msg.generation_id) {
      setPreviousGenerationResult(generationResult);
    }
    setGenerationResult({
      generation_id: msg.generation_id,
      master_image_url: msg.image_url,
      seed: msg.seed,
      compiled_prompt: msg.prompt,
      resolution: { width: 1080, height: 1620 },
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
      };

      const result = await composeWardrobe(payload);

      if (generationResult) {
        setPreviousGenerationResult(generationResult);
      }

      const nextGen = {
        generation_id: result.generation_id,
        master_image_url: result.image_url,
        seed: result.seed,
        compiled_prompt: result.compiled_prompt,
        resolution: result.resolution || { width: 1080, height: 1620 },
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
    const nextGen = {
      generation_id: result.generation_id,
      master_image_url: result.image_url,
      seed: result.seed,
      compiled_prompt: result.compiled_prompt,
      resolution: result.resolution || { width: 1080, height: 1620 },
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

    // Set immediate parent for Before/After split comparison in CanvasViewport
    if (lineageChain.length > 1) {
      const parent = lineageChain[lineageChain.length - 2];
      setPreviousGenerationResult({
        generation_id: parent.id,
        master_image_url: parent.master_image_url || parent.image_url,
        seed: parent.seed,
        compiled_prompt: parent.compiled_prompt || parent.prompt,
        resolution: { width: parent.resolution_width || 3840, height: parent.resolution_height || 3840 },
      });
    } else {
      setPreviousGenerationResult(null);
    }

    const restoredGen = {
      generation_id: record.id,
      master_image_url: record.master_image_url || record.image_url,
      seed: record.seed,
      compiled_prompt: record.compiled_prompt || record.prompt,
      resolution: { width: record.resolution_width || 3840, height: record.resolution_height || 3840 },
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

        {/* Header Actions */}
        <div className="header-actions">
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
          /* Step 1: Moodboard Upload & 4-Baseline Selector */
          <div className="step-1-layout">
            <MoodboardUploader
              files={files}
              onFilesChange={setFiles}
              prompt={baselinePrompt}
              onPromptChange={setBaselinePrompt}
              onAnalyze={handleAnalyzeAndGenerateBaselines}
              isAnalyzing={isAnalyzing}
              aspectRatio={aspectRatio}
              onAspectRatioChange={setAspectRatio}
            />

            {baselines.length > 0 ? (
              <BaselineSelector
                baselines={baselines}
                selectedBaselineId={activeBaseline?.id}
                onSelectBaseline={handleSelectBaseline}
                onProceedToStudio={handleProceedToStudio}
              />
            ) : (
              <div className="baseline-selector-container">
                <div className="viewport-empty-placeholder" style={{ padding: '60px 20px' }}>
                  <Layers size={48} className="placeholder-icon" />
                  <div className="placeholder-title">4 Baseline Image Candidates</div>
                  <div className="placeholder-subtitle">
                    Upload 1–5 moodboard images and provide your starting scene prompt to synthesize the Master Prompt, extract visual levers, and render 4 candidate seeds.
                  </div>
                </div>
              </div>
            )}
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
