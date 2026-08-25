import React, { useState, useEffect, useCallback } from 'react';
import {
  Sparkles,
  Layers,
  Paintbrush,
  History as HistoryIcon,
  AlertCircle,
  X,
} from 'lucide-react';

import MoodboardUploader from './components/MoodboardUploader';
import BaselineSelector from './components/BaselineSelector';
import TagStudio from './components/TagStudio';
import CanvasStudio from './components/CanvasStudio';
import CanvasViewport from './components/CanvasViewport';
import HistoryDrawer from './components/HistoryDrawer';
import ComparisonModal from './components/ComparisonModal';

import { DEFAULT_TAG_STATE } from './utils/defaultTags';
import { compileModularPrompt } from './utils/promptCompiler';
import {
  analyzeAndGenerateBaselines,
  fineTuneGeneration,
  exportBundle,
  fetchHistory,
  restoreGeneration,
} from './services/apiClient';

export default function App() {
  // Workflow step: 1 (Ingest & Baselines), 2 (Studio Workspace: Tag Studio & Canvas Studio)
  const [currentStep, setCurrentStep] = useState(1);

  // Ingest & Baselines state
  const [files, setFiles] = useState([]);
  const [baselinePrompt, setBaselinePrompt] = useState('');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [moodboardId, setMoodboardId] = useState(null);
  const [baselines, setBaselines] = useState([]);
  const [activeBaseline, setActiveBaseline] = useState(null);

  // Studio master TagState, Locks & Baseline Snapshot
  const [tagState, setTagState] = useState(DEFAULT_TAG_STATE);
  const [lockedCategories, setLockedCategories] = useState([]);
  const [baselineTagSnapshot, setBaselineTagSnapshot] = useState(null);
  const [useImageReference, setUseImageReference] = useState(true);

  // Studio workspace tab: 'tag' | 'canvas'
  const [studioTab, setStudioTab] = useState('tag');

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

  // Toggle locked category
  const handleToggleCategoryLock = (catKey) => {
    setLockedCategories((prev) => {
      if (prev.includes(catKey)) {
        return prev.filter((k) => k !== catKey);
      }
      return [...prev, catKey];
    });
  };

  // Reset tags back to original baseline snapshot
  const handleResetToBaseline = () => {
    if (baselineTagSnapshot) {
      setTagState({
        narrative: baselineTagSnapshot.narrative || '',
        categories: JSON.parse(JSON.stringify(baselineTagSnapshot.categories || {})),
        locked_categories: lockedCategories,
      });
    }
  };

  // Step 1: Analyze Moodboard & Generate 4 Baselines (with locked category preservation)
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
        tagState
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

  // Select Baseline & Advance to Step 2
  const handleSelectBaseline = (baseline) => {
    setActiveBaseline(baseline);
    setActiveSeed(baseline.seed);
  };

  const handleProceedToStudio = (baseline) => {
    if (baseline) {
      setActiveBaseline(baseline);
      setActiveSeed(baseline.seed);
      setPreviousGenerationResult(null);
      if (!baselineTagSnapshot) {
        setBaselineTagSnapshot(JSON.parse(JSON.stringify(tagState)));
      }
      const compiled = compileModularPrompt(tagState.narrative, tagState.categories);
      setGenerationResult({
        generation_id: baseline.id,
        master_image_url: baseline.image_url,
        seed: baseline.seed,
        compiled_prompt: baseline.compiled_prompt || compiled,
        resolution: baseline.resolution || { width: 1080, height: 1620 },
      });
    }
    setStudioTab('tag');
    setCurrentStep(2);
  };

  // Canvas Studio: Inpainting edit completed
  const handleInpaintComplete = async (result) => {
    if (!result) return;
    if (generationResult) {
      setPreviousGenerationResult(generationResult);
    }
    setGenerationResult({
      generation_id: result.generation_id,
      master_image_url: result.image_url,
      seed: result.seed,
      compiled_prompt: result.compiled_prompt,
      resolution: result.resolution || { width: 1080, height: 1620 },
    });
    await loadHistoryList();
  };

  // Step 2: Fine-Tune Re-Generation with Tag Studio & Prompt Compiler
  const handleGenerate = useCallback(async () => {
    setIsGenerating(true);
    setErrorMessage(null);

    try {
      const payload = {
        parent_id: activeBaseline?.id || generationResult?.generation_id || undefined,
        narrative: tagState.narrative,
        categories: tagState.categories,
        baseline_narrative: baselineTagSnapshot?.narrative,
        baseline_categories: baselineTagSnapshot?.categories,
        locked_categories: lockedCategories,
        seed_mode: seedMode,
        seed: activeSeed,
        use_image_reference: useImageReference,
        aspect_ratio: '2:3',
      };

      const result = await fineTuneGeneration(payload);
      if (generationResult) {
        setPreviousGenerationResult(generationResult);
      }
      setGenerationResult({
        generation_id: result.generation_id,
        master_image_url: result.image_url,
        seed: result.seed,
        compiled_prompt: result.compiled_prompt,
        resolution: result.resolution || { width: 1080, height: 1620 },
      });
      await loadHistoryList();
    } catch (err) {
      setErrorMessage(err.message || 'Fine-tune re-generation failed.');
    } finally {
      setIsGenerating(false);
    }
  }, [activeBaseline, generationResult, tagState, baselineTagSnapshot, lockedCategories, seedMode, activeSeed, useImageReference]);

  // Keyboard shortcut listener: Cmd/Ctrl + Enter
  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
        e.preventDefault();
        handleGenerate();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleGenerate]);

  // Export 5-Preset ZIP bundle
  const handleExportBundle = async (genId) => {
    if (!genId) return;
    setIsExporting(true);
    setErrorMessage(null);
    try {
      const blob = await exportBundle(genId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `bundle_${genId}.zip`;
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

  // Restore history record state
  const handleRestoreState = (record) => {
    if (record.schema_json && typeof record.schema_json === 'object') {
      if (record.schema_json.categories) {
        setTagState({
          narrative: record.schema_json.narrative || '',
          categories: record.schema_json.categories || {},
          locked_categories: lockedCategories,
        });
      }
    }
    if (record.seed) {
      setActiveSeed(record.seed);
    }

    if (record.is_baseline) {
      setActiveBaseline({
        id: record.id,
        image_url: record.master_image_url || record.image_url,
        seed: record.seed,
        compiled_prompt: record.compiled_prompt || record.prompt,
        resolution: { width: record.resolution_width || 1440, height: record.resolution_height || 1440 },
      });
      setPreviousGenerationResult(null);
    } else {
      const parent = history.find((h) => h.id === record.parent_id);
      if (parent) {
        setPreviousGenerationResult({
          generation_id: parent.id,
          master_image_url: parent.master_image_url || parent.image_url,
          seed: parent.seed,
          compiled_prompt: parent.compiled_prompt || parent.prompt,
          resolution: { width: parent.resolution_width || 1440, height: parent.resolution_height || 1440 },
        });
      }
      const rootBase = history.find(
        (h) => h.is_baseline && (h.id === record.parent_id || h.moodboard_id === record.moodboard_id)
      );
      if (rootBase) {
        setActiveBaseline({
          id: rootBase.id,
          image_url: rootBase.master_image_url || rootBase.image_url,
          seed: rootBase.seed,
          compiled_prompt: rootBase.compiled_prompt || rootBase.prompt,
        });
      }
    }

    setGenerationResult({
      generation_id: record.id,
      master_image_url: record.master_image_url || record.image_url,
      seed: record.seed,
      compiled_prompt: record.compiled_prompt || record.prompt,
      resolution: { width: record.resolution_width || 1440, height: record.resolution_height || 1440 },
    });
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

        {/* 2-Step Workflow Navigator */}
        <div className="step-nav-bar">
          <button
            type="button"
            className={`step-nav-btn ${currentStep === 1 ? 'active' : ''}`}
            onClick={() => setCurrentStep(1)}
          >
            <span>1. Moodboard & Baselines</span>
          </button>
          <button
            type="button"
            className={`step-nav-btn ${currentStep === 2 ? 'active' : ''}`}
            onClick={() => setCurrentStep(2)}
          >
            <span>2. Studio Workspace</span>
          </button>
        </div>

        {/* Header Actions */}
        <div className="header-actions">
          {currentStep === 2 && (
            <div style={{ display: 'flex', background: 'rgba(0,0,0,0.4)', borderRadius: 'var(--radius-sm)', padding: '2px' }}>
              <button
                type="button"
                className="btn"
                style={{
                  padding: '5px 12px',
                  fontSize: '0.78rem',
                  fontWeight: 600,
                  background: studioTab === 'tag' ? 'var(--accent-primary)' : 'transparent',
                  color: studioTab === 'tag' ? '#fff' : 'var(--text-muted)',
                  borderRadius: 'var(--radius-sm)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
                onClick={() => setStudioTab('tag')}
              >
                <Layers size={13} />
                <span>Macro Studio (Tags)</span>
              </button>
              <button
                type="button"
                className="btn"
                style={{
                  padding: '5px 12px',
                  fontSize: '0.78rem',
                  fontWeight: 600,
                  background: studioTab === 'canvas' ? 'var(--accent-primary)' : 'transparent',
                  color: studioTab === 'canvas' ? '#fff' : 'var(--text-muted)',
                  borderRadius: 'var(--radius-sm)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
                onClick={() => setStudioTab('canvas')}
              >
                <Paintbrush size={13} />
                <span>Micro Studio (Canvas)</span>
              </button>
            </div>
          )}

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
        <div
          style={{
            background: 'rgba(239, 68, 68, 0.15)',
            borderBottom: '1px solid rgba(239, 68, 68, 0.3)',
            padding: '10px 24px',
            color: '#f87171',
            fontSize: '0.85rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <AlertCircle size={16} />
            <span>{errorMessage}</span>
          </div>
          <button
            type="button"
            style={{ background: 'none', border: 'none', color: '#f87171', cursor: 'pointer' }}
            onClick={() => setErrorMessage(null)}
          >
            <X size={16} />
          </button>
        </div>
      )}

      {/* Main Studio Viewport */}
      <main className="studio-main-container">
        {currentStep === 1 ? (
          /* Step 1: Moodboard Upload & 4-Baseline Selector */
          <div className="step-1-layout">
            <MoodboardUploader
              files={files}
              onFilesChange={setFiles}
              prompt={baselinePrompt}
              onPromptChange={setBaselinePrompt}
              onAnalyze={handleAnalyzeAndGenerateBaselines}
              isAnalyzing={isAnalyzing}
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
                    Upload 1–5 moodboard images and provide your starting scene prompt to synthesize the Master Prompt, extract 9-category visual levers, and render 4 candidate seeds.
                  </div>
                </div>
              </div>
            )}
          </div>
        ) : (
          /* Step 2: Unified Workspace (Tag Studio or Canvas Studio + 4K Viewport) */
          <div className="workspace-grid">
            {/* Left Column */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', height: '100%' }}>
              {studioTab === 'tag' ? (
                <TagStudio
                  tagState={tagState}
                  onUpdateTagState={setTagState}
                  lockedCategories={lockedCategories}
                  onToggleCategoryLock={handleToggleCategoryLock}
                  baselineTagSnapshot={baselineTagSnapshot}
                  useImageReference={useImageReference}
                  onToggleImageReference={() => setUseImageReference((prev) => !prev)}
                  onResetToBaseline={handleResetToBaseline}
                />
              ) : (
                <CanvasStudio
                  imageUrl={generationResult?.master_image_url || activeBaseline?.image_url || null}
                  generationId={generationResult?.generation_id || activeBaseline?.id}
                  activeSeed={activeSeed}
                  onEditComplete={handleInpaintComplete}
                  onSwitchToGraph={() => setStudioTab('tag')}
                  onOpenHistory={() => setIsHistoryOpen(true)}
                  isInpainting={isInpainting}
                  setIsInpainting={setIsInpainting}
                />
              )}
            </div>

            {/* Right Column: 4K Master Viewport */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', height: '100%' }}>
              <div style={{ flex: 1, minHeight: '600px' }}>
                <CanvasViewport
                  imageUrl={generationResult?.master_image_url || activeBaseline?.image_url || null}
                  beforeImageUrl={previousGenerationResult?.master_image_url || activeBaseline?.image_url || null}
                  baselineImageUrl={activeBaseline?.image_url || null}
                  beforeLabel={
                    previousGenerationResult && previousGenerationResult.generation_id !== activeBaseline?.id
                      ? 'Previous Iteration'
                      : 'Baseline'
                  }
                  afterLabel={studioTab === 'canvas' ? 'Inpaint Edit' : 'Current Iteration'}
                  isGenerating={studioTab === 'canvas' ? isInpainting : isGenerating}
                  isInpaintMode={studioTab === 'canvas'}
                  isExporting={isExporting}
                  generationResult={generationResult}
                  previousGenerationResult={previousGenerationResult}
                  activeSeed={activeSeed}
                  seedMode={seedMode}
                  onGenerate={handleGenerate}
                  onExportBundle={handleExportBundle}
                  onOpenHistory={() => setIsHistoryOpen(true)}
                  canGenerate={true}
                  mode={studioTab}
                />
              </div>
            </div>
          </div>
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
