import { useState, useCallback } from 'react';
import { getMasterResolution } from '../components/BaselineSelector';
import { fetchHistory, fetchConversation } from '../services/apiClient';

/**
 * Hook for managing Lineage History, ancestor reconstruction, and side-by-side comparisons.
 */
export function useLineageHistory({
  aspectRatio,
  onAspectRatioChange,
  setActiveSeed,
  setActiveBaseline,
  setPreviousGenerationResult,
  setGenerationResult,
  setConversationId,
  setConversationMessages,
  setCurrentStep,
}) {
  const [history, setHistory] = useState([]);
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [selectedForCompare, setSelectedForCompare] = useState([]);
  const [isCompareOpen, setIsCompareOpen] = useState(false);

  const loadHistoryList = useCallback(async () => {
    try {
      const res = await fetchHistory();
      if (res && res.generations) {
        setHistory(res.generations);
      }
    } catch (err) {
      console.error('Failed to load history:', err);
    }
  }, []);

  const handleToggleCompare = useCallback((id) => {
    setSelectedForCompare((prev) => {
      if (prev.includes(id)) {
        return prev.filter((item) => item !== id);
      }
      if (prev.length >= 2) return prev;
      return [...prev, id];
    });
  }, []);

  const handleRestoreState = useCallback(
    async (record) => {
      setActiveSeed(record.seed);

      // Reconstruct full ancestor lineage chain from history
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

      const targetRatio = record.aspect_ratio || aspectRatio || '1:1';
      const masterRes = getMasterResolution(targetRatio);

      if (record.aspect_ratio && onAspectRatioChange) {
        onAspectRatioChange(record.aspect_ratio);
      }

      const parent = history.find((h) => h.id === record.parent_id);
      if (parent) {
        const parentRatio = parent.aspect_ratio || targetRatio;
        const parentMasterRes = getMasterResolution(parentRatio);
        setPreviousGenerationResult({
          generation_id: parent.id,
          master_image_url: parent.master_image_url || parent.image_url,
          seed: parent.seed,
          compiled_prompt: parent.compiled_prompt || parent.prompt,
          aspect_ratio: parentRatio,
          resolution: {
            width: parent.resolution_width || parentMasterRes.width,
            height: parent.resolution_height || parentMasterRes.height,
          },
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
        resolution: {
          width: record.resolution_width || masterRes.width,
          height: record.resolution_height || masterRes.height,
        },
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
        const reconstructed = lineageChain.map((item, idx) => ({
          role: idx === 0 && item.is_baseline ? 'baseline' : 'user',
          prompt:
            item.compiled_prompt || item.prompt || (item.is_baseline ? 'Initial Baseline' : 'Iterative Refinement'),
          generation_id: item.id,
          image_url: item.master_image_url || item.image_url,
          seed: item.seed,
          created_at: item.created_at || new Date().toISOString(),
          is_inpaint:
            item.id?.startsWith('gen_inpaint_') || Boolean(item.inpaint_metadata || item.schema_json?.inpaint_metadata),
          is_wardrobe: Boolean(item.schema_json?.wardrobe_composition),
          is_prop: Boolean(item.schema_json?.prop_composition),
        }));
        setConversationMessages(reconstructed);
        setConversationId(convId || `conv_${record.id}`);
      }

      setIsHistoryOpen(false);
      setCurrentStep((prev) => (prev === 1 || prev === 4 ? 2 : prev));
    },
    [
      history,
      aspectRatio,
      setActiveSeed,
      setActiveBaseline,
      setPreviousGenerationResult,
      setGenerationResult,
      setConversationId,
      setConversationMessages,
      setCurrentStep,
    ]
  );

  const compareVersionA = history.find((h) => h.id === selectedForCompare[0]);
  const compareVersionB = history.find((h) => h.id === selectedForCompare[1]);

  return {
    history,
    isHistoryOpen,
    setIsHistoryOpen,
    selectedForCompare,
    setSelectedForCompare,
    isCompareOpen,
    setIsCompareOpen,
    loadHistoryList,
    handleToggleCompare,
    handleRestoreState,
    compareVersionA,
    compareVersionB,
  };
}
