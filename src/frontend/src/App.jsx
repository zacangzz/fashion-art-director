import React, { useState, useEffect, useCallback } from 'react';
import {
  Sparkles,
  Layers,
  Activity,
  History as HistoryIcon,
  AlertCircle,
  X,
  Eye,
  Cpu,
  LogOut,
  Users as UsersIcon,
  VenetianMask,
} from 'lucide-react';

import MoodboardUploader from './components/MoodboardUploader';
import PromptReviewSection from './components/PromptReviewSection';
import BaselineSelector, { getBaseResolution } from './components/BaselineSelector';
import RefinementChat from './components/RefinementChat';
import WardrobePanel from './components/WardrobePanel';
import CanvasStudio from './components/CanvasStudio';
import CanvasViewport from './components/CanvasViewport';
import ExportStudio from './components/ExportStudio';
import HistoryDrawer from './components/HistoryDrawer';
import ComparisonModal from './components/ComparisonModal';
import AuthPortal from './components/AuthPortal';
import AdminPortalModal from './components/AdminPortalModal';
import ProxyBanner from './components/ProxyBanner';
import WorkflowToolbar from './components/WorkflowToolbar';
import { useAuth } from './contexts/AuthContext';
import { compileModularPrompt } from './utils/promptCompiler';

// Domain Custom Hooks
import { useModelConfig } from './hooks/useModelConfig';
import { useMoodboardAnalysis } from './hooks/useMoodboardAnalysis';
import { useRefinementStudio } from './hooks/useRefinementStudio';
import { useWardrobeComposer } from './hooks/useWardrobeComposer';
import { useLineageHistory } from './hooks/useLineageHistory';

export default function App() {
  const { currentUser, userProfile, loading, signOutUser } = useAuth();
  const [isAdminModalOpen, setIsAdminModalOpen] = useState(false);
  const [currentStep, setCurrentStep] = useState(1);
  const [errorMessage, setErrorMessage] = useState(null);
  const [activeAspectRatio, setActiveAspectRatio] = useState('1:1');

  // 1. Model Configuration Hook
  const {
    modelConfig,
    visionModel,
    imagenModel,
    loadModelConfig,
    handleVisionModelChange,
    handleImagenModelChange,
  } = useModelConfig();

  // 2. Refinement & Viewport State Hook
  const refinement = useRefinementStudio({
    imagenModel,
    aspectRatio: activeAspectRatio,
    onAspectRatioChange: setActiveAspectRatio,
    activeBaseline: null,
    onError: setErrorMessage,
    onHistoryRefresh: () => historyHook.loadHistoryList(),
  });

  // Direct photo upload callback
  const handleDirectPhotoReady = useCallback((response, effRatio) => {
    const ratio = effRatio || response.aspect_ratio || activeAspectRatio || '1:1';
    setActiveAspectRatio(ratio);
    refinement.setActiveSeed(response.seed);
    refinement.setPreviousGenerationResult(null);

    const initialGen = {
      generation_id: response.generation_id,
      master_image_url: response.image_url,
      seed: response.seed,
      compiled_prompt: response.compiled_prompt,
      aspect_ratio: ratio,
      resolution: response.resolution || getBaseResolution(ratio),
    };
    refinement.setGenerationResult(initialGen);

    const baseMsg = {
      role: 'baseline',
      prompt: response.compiled_prompt,
      generation_id: response.generation_id,
      image_url: response.image_url,
      seed: response.seed,
      created_at: response.created_at || new Date().toISOString(),
      aspect_ratio: ratio,
    };
    refinement.setConversationMessages([baseMsg]);
    refinement.setConversationId(`conv_${response.generation_id}`);
    setCurrentStep(2);
  }, [activeAspectRatio, refinement.setActiveSeed, refinement.setPreviousGenerationResult, refinement.setGenerationResult, refinement.setConversationMessages, refinement.setConversationId]);

  // 3. Moodboard Ingestion & 9-Category Levers Hook
  const moodboard = useMoodboardAnalysis({
    visionModel,
    imagenModel,
    aspectRatio: activeAspectRatio,
    onAspectRatioChange: setActiveAspectRatio,
    onError: setErrorMessage,
    onBaselineReady: (baseline) => {
      if (baseline) {
        refinement.setActiveSeed(baseline.seed);
        if (baseline.aspect_ratio) {
          setActiveAspectRatio(baseline.aspect_ratio);
        }
      }
    },
    onDirectPhotoReady: handleDirectPhotoReady,
    onHistoryRefresh: () => historyHook.loadHistoryList(),
  });

  // 4. Lineage History Hook
  const historyHook = useLineageHistory({
    aspectRatio: activeAspectRatio,
    onAspectRatioChange: setActiveAspectRatio,
    setActiveSeed: refinement.setActiveSeed,
    setActiveBaseline: moodboard.setActiveBaseline,
    setPreviousGenerationResult: refinement.setPreviousGenerationResult,
    setGenerationResult: refinement.setGenerationResult,
    setConversationId: refinement.setConversationId,
    setConversationMessages: refinement.setConversationMessages,
    setCurrentStep,
  });

  // Callback when a direct photo or baseline is selected/ready
  const handleProceedToStudio = useCallback((baseline) => {
    if (baseline) {
      moodboard.setActiveBaseline(baseline);
      refinement.setActiveSeed(baseline.seed);
      refinement.setPreviousGenerationResult(null);

      const compiled =
        baseline.compiled_prompt ||
        moodboard.masterPrompt ||
        compileModularPrompt(moodboard.tagState.categories);
      const effRatio = baseline.aspect_ratio || activeAspectRatio || '1:1';
      setActiveAspectRatio(effRatio);

      const initialGen = {
        generation_id: baseline.id,
        master_image_url: baseline.image_url,
        seed: baseline.seed,
        compiled_prompt: compiled,
        aspect_ratio: effRatio,
        resolution: baseline.resolution || getBaseResolution(effRatio),
      };
      refinement.setGenerationResult(initialGen);

      const baseMsg = {
        role: 'baseline',
        prompt: compiled,
        generation_id: baseline.id,
        image_url: baseline.image_url,
        seed: baseline.seed,
        created_at: baseline.created_at || new Date().toISOString(),
        aspect_ratio: effRatio,
      };
      refinement.setConversationMessages([baseMsg]);
      refinement.setConversationId(`conv_${baseline.id}`);
    }
    setCurrentStep(2);
  }, [activeAspectRatio, moodboard.setActiveBaseline, moodboard.masterPrompt, moodboard.tagState.categories, refinement.setActiveSeed, refinement.setPreviousGenerationResult, refinement.setGenerationResult, refinement.setConversationMessages, refinement.setConversationId]);

  // 5. Wardrobe Composition Hook
  const wardrobe = useWardrobeComposer({
    visionModel,
    imagenModel,
    aspectRatio: activeAspectRatio,
    onAspectRatioChange: setActiveAspectRatio,
    generationResult: refinement.generationResult,
    activeBaseline: moodboard.activeBaseline,
    activeSeed: refinement.activeSeed,
    seedMode: refinement.seedMode,
    conversationId: refinement.conversationId,
    setPreviousGenerationResult: refinement.setPreviousGenerationResult,
    setGenerationResult: refinement.setGenerationResult,
    setActiveSeed: refinement.setActiveSeed,
    setConversationId: refinement.setConversationId,
    setConversationMessages: refinement.setConversationMessages,
    onError: setErrorMessage,
    onHistoryRefresh: () => historyHook.loadHistoryList(),
  });

  // Load session data on approval
  useEffect(() => {
    if (currentUser && userProfile?.status === 'approved') {
      historyHook.loadHistoryList();
      loadModelConfig();
    }
  }, [currentUser, userProfile?.status, historyHook.loadHistoryList, loadModelConfig]);

  const hasActiveImage = Boolean(
    refinement.generationResult?.master_image_url || moodboard.activeBaseline?.image_url
  );

  // Reload history and assets whenever the active user or proxy identity switches
  useEffect(() => {
    if (userProfile?.id || userProfile?.uid) {
      historyHook.loadHistoryList();
    }
  }, [userProfile?.id, userProfile?.uid]);

  // 1. Loading Splash
  if (loading) {
    return (
      <div className="min-h-screen w-full flex flex-col items-center justify-center bg-[#07090e] text-slate-100 gap-4 font-sans select-none">
        <div className="p-4 rounded-3xl bg-gradient-to-tr from-cyan-500/20 via-slate-800 to-purple-500/20 border border-cyan-500/30 text-cyan-400 shadow-xl shadow-cyan-500/10">
          <Sparkles size={32} className="animate-spin" />
        </div>
        <div className="flex flex-col items-center gap-1">
          <span className="text-xs font-mono uppercase tracking-[0.25em] text-cyan-400 font-semibold">
            Fashion Art Director Studio
          </span>
          <span className="text-[11px] font-mono text-slate-500">
            Verifying security credentials & whitelist...
          </span>
        </div>
      </div>
    );
  }

  // 2. Lock app behind AuthPortal if unauthenticated or not approved
  if (!currentUser || !userProfile || userProfile.status !== 'approved') {
    return <AuthPortal />;
  }

  const hasAdminAccess = Boolean(
    userProfile?.is_admin ||
    userProfile?.is_proxy ||
    userProfile?.real_user?.is_admin
  );

  return (
    <div className="app-container">
      {/* Top Luxury Proxy HUD Banner (Active only during proxy mode) */}
      <ProxyBanner onOpenAdminModal={() => setIsAdminModalOpen(true)} />

      {/* Top Header */}
      <header className="header">
        <div className="header-brand">
          <div className="header-logo" title="mise en scène">
            <Sparkles size={16} />
          </div>
          <span className="header-title">mise en scène</span>
        </div>

        {/* 5-Step Sequential Workflow Navigator */}
        <nav className="step-nav-bar" aria-label="Studio Workflow Steps">
          <button
            type="button"
            className={`step-nav-btn ${currentStep === 1 ? 'active' : ''}`}
            onClick={() => setCurrentStep(1)}
          >
            <span className="step-num">01</span>
            <span>Art Direction</span>
          </button>

          <button
            type="button"
            className={`step-nav-btn ${currentStep === 2 ? 'active' : ''}`}
            onClick={() => setCurrentStep(2)}
            disabled={!hasActiveImage}
          >
            <span className="step-num">02</span>
            <span>Refinement</span>
          </button>

          <button
            type="button"
            className={`step-nav-btn ${currentStep === 3 ? 'active' : ''}`}
            onClick={() => setCurrentStep(3)}
            disabled={!hasActiveImage}
          >
            <span className="step-num">03</span>
            <span>Canvas</span>
          </button>

          <button
            type="button"
            className={`step-nav-btn ${currentStep === 4 ? 'active' : ''}`}
            onClick={() => setCurrentStep(4)}
            disabled={!hasActiveImage}
          >
            <span className="step-num">04</span>
            <span>Wardrobe</span>
          </button>

          <button
            type="button"
            className={`step-nav-btn ${currentStep === 5 ? 'active' : ''}`}
            onClick={() => setCurrentStep(5)}
            disabled={!hasActiveImage}
          >
            <span className="step-num">05</span>
            <span>Export</span>
          </button>
        </nav>

        {/* Header Model Selectors & Utilities */}
        <div className="header-actions">
          <div className="model-selectors-container">
            <div className="model-selector-chip" title="Vision Model for Analysis, Directing & Pin Grounding">
              <Eye size={13} className="text-cyan-400 shrink-0" />
              <select
                className="model-select-input"
                value={visionModel}
                onChange={(e) => handleVisionModelChange(e.target.value)}
                aria-label="Vision Model"
              >
                {modelConfig.available_vision_models.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            </div>

            <div className="model-selector-chip" title="Image Model for Baselines, Fine-Tuning & Refinement">
              <Cpu size={13} className="text-amber-400 shrink-0" />
              <select
                className="model-select-input"
                value={imagenModel}
                onChange={(e) => handleImagenModelChange(e.target.value)}
                aria-label="Image Generation Model"
              >
                {modelConfig.available_imagen_models.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="nav-utilities-container">
            <a
              href="/telemetry"
              target="_blank"
              rel="noopener noreferrer"
              className="nav-utility-btn"
              title="Studio Observability, Telemetry & Logs"
              aria-label="Observability & Logs"
            >
              <Activity size={16} className="text-indigo-400" />
            </a>

            <button
              type="button"
              className="nav-utility-btn"
              onClick={() => historyHook.setIsHistoryOpen(true)}
              title={`Lineage History (${historyHook.history.length})`}
              aria-label="Lineage History"
            >
              <HistoryIcon size={16} className="text-slate-300" />
            </button>

            {currentUser && (
              <div className="user-nav-group">
                {hasAdminAccess && (
                  <button
                    type="button"
                    onClick={() => setIsAdminModalOpen(true)}
                    className="admin-nav-btn"
                    title="Studio Whitelist & Team Management"
                    aria-label="Studio Whitelist"
                  >
                    <UsersIcon size={13} />
                    <span>Admin</span>
                  </button>
                )}

                <div
                  className={`user-profile-chip ${userProfile?.is_proxy ? 'user-profile-chip-proxy' : ''}`}
                  title={
                    userProfile?.is_proxy
                      ? `Acting as ${userProfile.display_name || userProfile.email} (Proxied by ${userProfile.proxied_by?.email || 'Admin'})`
                      : `Signed in as ${currentUser.email || currentUser.displayName || 'User'}`
                  }
                >
                  <div className="user-profile-avatar">
                    {userProfile?.is_proxy ? (
                      <VenetianMask size={13} style={{ color: '#f59e0b' }} />
                    ) : (
                      (currentUser.email || currentUser.displayName || 'U')[0]
                    )}
                  </div>
                  <span className="user-profile-name">
                    {userProfile?.display_name || currentUser.displayName || currentUser.email?.split('@')[0]}
                  </span>
                  {userProfile?.is_proxy && (
                    <span className="proxy-pill-tag">Proxy</span>
                  )}
                </div>

                <button
                  type="button"
                  onClick={signOutUser}
                  className="nav-utility-btn"
                  title="Sign Out"
                  aria-label="Sign Out"
                  style={{ color: '#f87171' }}
                >
                  <LogOut size={14} />
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Error Alert Banner */}
      {errorMessage && (
        <div className="error-banner" role="alert">
          <div className="error-banner-content">
            <AlertCircle size={16} />
            <span>{errorMessage}</span>
          </div>
          <button
            type="button"
            className="error-banner-close"
            onClick={() => setErrorMessage(null)}
            aria-label="Close error alert"
          >
            <X size={16} />
          </button>
        </div>
      )}

      {/* Main Studio Views */}
      <main className="studio-main-container">
        {/* Reusable Workflow Context & Aspect Ratio Toolbar */}
        <WorkflowToolbar
          aspectRatio={activeAspectRatio}
          onAspectRatioChange={setActiveAspectRatio}
          activeSeed={refinement.activeSeed}
          seedMode={refinement.seedMode}
          onSeedModeChange={refinement.setSeedMode}
          disabled={refinement.isGenerating || moodboard.isGeneratingBaselines || moodboard.isAnalyzing || wardrobe.isComposingWardrobe}
        />

        {currentStep === 1 && (
          <div className="step-1-layout">
            <MoodboardUploader
              files={moodboard.files}
              onFilesChange={moodboard.setFiles}
              prompt={moodboard.baselinePrompt}
              onPromptChange={moodboard.setBaselinePrompt}
              onAnalyze={moodboard.handleAnalyzeMoodboard}
              isAnalyzing={moodboard.isAnalyzing}
              aspectRatio={activeAspectRatio}
              onAspectRatioChange={setActiveAspectRatio}
              onDirectPhotoUpload={moodboard.handleDirectPhotoUpload}
              isDirectUploading={moodboard.isDirectUploading}
            />

            <div className="step-1-right-column">
              {moodboard.moodboardId ||
              moodboard.masterPrompt ||
              (moodboard.tagState?.categories && Object.keys(moodboard.tagState.categories).length > 0) ? (
                <>
                  <PromptReviewSection
                    tagState={moodboard.tagState}
                    onUpdateTagState={moodboard.setTagState}
                    masterPrompt={moodboard.masterPrompt}
                    onMasterPromptChange={moodboard.setMasterPrompt}
                    aspectRatio={moodboard.aspectRatio}
                    temperature={moodboard.temperature}
                    onTemperatureChange={moodboard.setTemperature}
                    conflicts={moodboard.promptConflicts}
                    isCheckingConflicts={moodboard.isCheckingConflicts}
                    onCheckConflicts={moodboard.handleCheckConflicts}
                    isResyncing={moodboard.isResyncingPrompt || moodboard.isResyncingLevers}
                    isResyncingPrompt={moodboard.isResyncingPrompt}
                    onResyncPromptFromLevers={moodboard.handleResyncPromptFromLevers}
                    isResyncingLevers={moodboard.isResyncingLevers}
                    onResyncLeversFromPrompt={moodboard.handleResyncLeversFromPrompt}
                    onResyncPrompt={moodboard.handleResyncPromptFromLevers}
                    isGeneratingBaselines={moodboard.isGeneratingBaselines}
                    onGenerateBaselines={moodboard.handleGenerateBaselines}
                    hasBaselines={moodboard.baselines.length > 0}
                  />

                  {moodboard.baselines.length > 0 ? (
                    <BaselineSelector
                      baselines={moodboard.baselines}
                      selectedBaselineId={moodboard.activeBaseline?.id}
                      onSelectBaseline={moodboard.handleSelectBaseline}
                      onProceedToStudio={handleProceedToStudio}
                      tagState={moodboard.tagState}
                      aspectRatio={moodboard.aspectRatio}
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
          <div className="workspace-grid">
            <div className="workspace-left-column">
              <RefinementChat
                conversationMessages={refinement.conversationMessages}
                onSendRefinement={refinement.handleSendRefinement}
                isGenerating={refinement.isGenerating}
                activeSeed={refinement.activeSeed}
                seedMode={refinement.seedMode}
                onSeedModeChange={refinement.setSeedMode}
                onSeedChange={refinement.setActiveSeed}
                activeGenerationId={refinement.generationResult?.generation_id}
                onSelectMessage={refinement.handleSelectMessage}
                onToggleWardrobe={() => setCurrentStep(4)}
                isWardrobeOpen={false}
                assignmentCount={wardrobe.wardrobeAssignments.length}
              />
            </div>

            <div className="workspace-right-column">
              <div className="workspace-viewport-wrapper">
                <CanvasViewport
                  imageUrl={refinement.generationResult?.master_image_url || moodboard.activeBaseline?.image_url || null}
                  beforeImageUrl={refinement.previousGenerationResult?.master_image_url || moodboard.activeBaseline?.image_url || null}
                  baselineImageUrl={moodboard.activeBaseline?.image_url || null}
                  beforeLabel={
                    refinement.previousGenerationResult &&
                    refinement.previousGenerationResult.generation_id !== moodboard.activeBaseline?.id
                      ? 'Previous Iteration'
                      : 'Baseline'
                  }
                  afterLabel="Refined Output"
                  isGenerating={refinement.isGenerating}
                  generationResult={refinement.generationResult}
                  previousGenerationResult={refinement.previousGenerationResult}
                  activeSeed={refinement.activeSeed}
                  seedMode={refinement.seedMode}
                  onOpenHistory={() => historyHook.setIsHistoryOpen(true)}
                  canGenerate={false}
                  mode="refinement"
                  wardrobeAssignments={wardrobe.wardrobeAssignments}
                  onDropGarment={wardrobe.handleAddWardrobeAssignment}
                  onRemovePin={wardrobe.handleRemoveWardrobeAssignment}
                  onUpdatePinPosition={wardrobe.handleUpdateWardrobePosition}
                  isWardrobeMode={false}
                />
              </div>
            </div>
          </div>
        )}

        {currentStep === 3 && (
          <div className="workspace-grid inpaint-workspace-grid">
            <div className="workspace-left-column">
              <CanvasStudio
                imageUrl={refinement.generationResult?.master_image_url || moodboard.activeBaseline?.image_url || null}
                generationId={refinement.generationResult?.generation_id || moodboard.activeBaseline?.id}
                activeSeed={refinement.activeSeed}
                aspectRatio={activeAspectRatio}
                onEditComplete={refinement.handleInpaintComplete}
                onSwitchToGraph={() => setCurrentStep(2)}
                onOpenHistory={() => historyHook.setIsHistoryOpen(true)}
                isInpainting={refinement.isInpainting}
                setIsInpainting={refinement.setIsInpainting}
              />
            </div>

            <div className="workspace-right-column">
              <div className="workspace-viewport-wrapper">
                <CanvasViewport
                  imageUrl={refinement.generationResult?.master_image_url || moodboard.activeBaseline?.image_url || null}
                  beforeImageUrl={refinement.previousGenerationResult?.master_image_url || moodboard.activeBaseline?.image_url || null}
                  baselineImageUrl={moodboard.activeBaseline?.image_url || null}
                  beforeLabel={
                    refinement.previousGenerationResult &&
                    refinement.previousGenerationResult.generation_id !== moodboard.activeBaseline?.id
                      ? 'Before Inpaint'
                      : 'Baseline'
                  }
                  afterLabel="Inpainted Output"
                  isGenerating={refinement.isInpainting}
                  isInpaintMode={true}
                  generationResult={refinement.generationResult}
                  previousGenerationResult={refinement.previousGenerationResult}
                  activeSeed={refinement.activeSeed}
                  seedMode={refinement.seedMode}
                  onOpenHistory={() => historyHook.setIsHistoryOpen(true)}
                  canGenerate={false}
                  mode="canvas"
                />
              </div>
            </div>
          </div>
        )}

        {currentStep === 4 && (
          <div className="workspace-grid wardrobe-workspace-grid">
            <div className="workspace-left-column">
              <WardrobePanel
                isOpen={true}
                onClose={() => setCurrentStep(2)}
                assignments={wardrobe.wardrobeAssignments}
                onAddAssignment={wardrobe.handleAddWardrobeAssignment}
                onRemoveAssignment={wardrobe.handleRemoveWardrobeAssignment}
                onClearAssignments={wardrobe.handleClearWardrobeAssignments}
                onCompose={wardrobe.handleComposeWardrobe}
                isComposing={wardrobe.isComposingWardrobe}
                activeGenerationId={refinement.generationResult?.generation_id || moodboard.activeBaseline?.id}
                visionModel={visionModel}
              />
            </div>

            <div className="workspace-right-column">
              <div className="workspace-viewport-wrapper">
                <CanvasViewport
                  imageUrl={refinement.generationResult?.master_image_url || moodboard.activeBaseline?.image_url || null}
                  beforeImageUrl={refinement.previousGenerationResult?.master_image_url || moodboard.activeBaseline?.image_url || null}
                  baselineImageUrl={moodboard.activeBaseline?.image_url || null}
                  beforeLabel={
                    refinement.previousGenerationResult &&
                    refinement.previousGenerationResult.generation_id !== moodboard.activeBaseline?.id
                      ? 'Previous Output'
                      : 'Baseline'
                  }
                  afterLabel="Wardrobe Output"
                  isGenerating={wardrobe.isComposingWardrobe}
                  generationResult={refinement.generationResult}
                  previousGenerationResult={refinement.previousGenerationResult}
                  activeSeed={refinement.activeSeed}
                  seedMode={refinement.seedMode}
                  onOpenHistory={() => historyHook.setIsHistoryOpen(true)}
                  canGenerate={false}
                  mode="wardrobe"
                  wardrobeAssignments={wardrobe.wardrobeAssignments}
                  onDropGarment={wardrobe.handleAddWardrobeAssignment}
                  onRemovePin={wardrobe.handleRemoveWardrobeAssignment}
                  onUpdatePinPosition={wardrobe.handleUpdateWardrobePosition}
                  isWardrobeMode={true}
                />
              </div>
            </div>
          </div>
        )}

        {currentStep === 5 && (
          <ExportStudio
            generationResult={refinement.generationResult}
            activeBaseline={moodboard.activeBaseline}
            globalAspectRatio={activeAspectRatio}
            history={historyHook.history}
            onExportMasterPrepared={(result) => {
              refinement.setGenerationResult(result);
              historyHook.loadHistoryList();
            }}
          />
        )}
      </main>

      {/* Slide-out History Lineage Drawer */}
      <HistoryDrawer
        isOpen={historyHook.isHistoryOpen}
        onClose={() => historyHook.setIsHistoryOpen(false)}
        history={historyHook.history}
        activeGenerationId={refinement.generationResult?.generation_id}
        onRestoreGeneration={historyHook.handleRestoreState}
        selectedForCompare={historyHook.selectedForCompare}
        onToggleCompare={historyHook.handleToggleCompare}
        onOpenCompareModal={() => historyHook.setIsCompareOpen(true)}
      />

      {/* Side-by-Side Comparison Modal */}
      {historyHook.isCompareOpen && historyHook.compareVersionA && historyHook.compareVersionB && (
        <ComparisonModal
          isOpen={historyHook.isCompareOpen}
          onClose={() => historyHook.setIsCompareOpen(false)}
          versionA={historyHook.compareVersionA}
          versionB={historyHook.compareVersionB}
        />
      )}

      {/* Admin Portal Modal */}
      {isAdminModalOpen && (
        <AdminPortalModal
          isOpen={isAdminModalOpen}
          onClose={() => setIsAdminModalOpen(false)}
        />
      )}
    </div>
  );
}
