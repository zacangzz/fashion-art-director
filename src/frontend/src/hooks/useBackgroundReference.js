import { useState, useCallback, useEffect } from 'react';
import {
  uploadBackgroundReference,
  fetchBackgroundReferences,
  deleteBackgroundReference,
} from '../services/apiClient';

const DEFAULT_STAGING_PARAMS = {
  subject_x: 0.5,
  subject_y: 0.65,
  camera_x: 0.5,
  camera_y: 0.9,
  camera_angle: 'facing_window',
  focal_length_mm: 35,
  zoom_level: 'environmental',
};

/**
 * Domain custom hook for managing reference background uploads, reusable library,
 * perspective & photometric harmonization, and interactive 2D/3D camera staging.
 */
export function useBackgroundReference({ onError } = {}) {
  const [backgroundLibrary, setBackgroundLibrary] = useState([]);
  const [activeBackground, setActiveBackground] = useState(null);
  const [perspectiveMode, setPerspectiveMode] = useState('auto_align');
  const [depthOfField, setDepthOfField] = useState('natural');
  const [lightingMode, setLightingMode] = useState('harmonize_ambient');
  const [spatialStaging, setSpatialStaging] = useState(DEFAULT_STAGING_PARAMS);
  const [isStagingConfigured, setIsStagingConfigured] = useState(false);
  const [isLibraryOpen, setIsLibraryOpen] = useState(false);
  const [isStagerModalOpen, setIsStagerModalOpen] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [isLoadingLibrary, setIsLoadingLibrary] = useState(false);

  // Load reusable background library
  const loadLibrary = useCallback(async () => {
    setIsLoadingLibrary(true);
    try {
      const res = await fetchBackgroundReferences();
      if (res && Array.isArray(res.items)) {
        setBackgroundLibrary(res.items);
      }
    } catch (err) {
      console.warn('Failed to load background library:', err);
    } finally {
      setIsLoadingLibrary(false);
    }
  }, []);

  // Upload a new background reference and immediately attach it
  const handleUploadBackground = useCallback(async (file) => {
    if (!file) return null;
    setIsUploading(true);
    onError?.(null);

    try {
      const uploaded = await uploadBackgroundReference(file);
      const newBg = {
        id: uploaded.id,
        image_url: uploaded.image_url,
        thumbnail_url: uploaded.thumbnail_url || uploaded.image_url,
        original_filename: uploaded.original_filename,
        aspect_ratio: uploaded.aspect_ratio,
        created_at: uploaded.created_at,
      };

      setBackgroundLibrary((prev) => [newBg, ...prev.filter((b) => b.id !== newBg.id)]);
      setActiveBackground(newBg);
      setIsStagingConfigured(false);
      return newBg;
    } catch (err) {
      onError?.(err.message || 'Failed to upload background reference.');
      return null;
    } finally {
      setIsUploading(false);
    }
  }, [onError]);

  // Select an existing background reference from the library
  const handleSelectBackground = useCallback((bg) => {
    setActiveBackground(bg);
    setIsStagingConfigured(false);
    setIsLibraryOpen(false);
  }, []);

  // Remove the currently attached background reference
  const handleRemoveActiveBackground = useCallback(() => {
    setActiveBackground(null);
    setIsStagingConfigured(false);
  }, []);

  // Delete background reference from storage and library
  const handleDeleteBackground = useCallback(async (bgId) => {
    if (!bgId) return;
    try {
      await deleteBackgroundReference(bgId);
      setBackgroundLibrary((prev) => prev.filter((b) => b.id !== bgId));
      if (activeBackground?.id === bgId) {
        setActiveBackground(null);
        setIsStagingConfigured(false);
      }
    } catch (err) {
      onError?.(err.message || 'Failed to delete background reference.');
    }
  }, [activeBackground?.id, onError]);

  // Update spatial staging coordinates and camera vector
  const updateSpatialStaging = useCallback((params) => {
    setSpatialStaging((prev) => ({ ...prev, ...params }));
    setIsStagingConfigured(true);
  }, []);

  // Reset all background parameters
  const handleResetBackground = useCallback(() => {
    setActiveBackground(null);
    setPerspectiveMode('auto_align');
    setDepthOfField('natural');
    setLightingMode('harmonize_ambient');
    setSpatialStaging(DEFAULT_STAGING_PARAMS);
    setIsStagingConfigured(false);
  }, []);

  return {
    backgroundLibrary,
    activeBackground,
    setActiveBackground,
    perspectiveMode,
    setPerspectiveMode,
    depthOfField,
    setDepthOfField,
    lightingMode,
    setLightingMode,
    spatialStaging,
    updateSpatialStaging,
    setSpatialStaging,
    isStagingConfigured,
    setIsStagingConfigured,
    isLibraryOpen,
    setIsLibraryOpen,
    isStagerModalOpen,
    setIsStagerModalOpen,
    isUploading,
    isLoadingLibrary,
    loadLibrary,
    handleUploadBackground,
    handleSelectBackground,
    handleRemoveActiveBackground,
    handleDeleteBackground,
    handleResetBackground,
  };
}
