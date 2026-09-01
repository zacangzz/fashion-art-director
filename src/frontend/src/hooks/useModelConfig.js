import { useState, useCallback } from 'react';
import { fetchModelConfig } from '../services/apiClient';

/**
 * Hook for managing dynamic Google GenAI model configurations.
 */
export function useModelConfig() {
  const [modelConfig, setModelConfig] = useState({
    available_vision_models: ['gemini-3.5-flash-lite', 'gemini-3.7-flash'],
    available_imagen_models: ['gemini-3.1-flash-lite-image', 'gemini-3.1-flash-image', 'gemini-3-pro-image'],
    default_vision_model: 'gemini-3.5-flash-lite',
    default_imagen_model: 'gemini-3.1-flash-image',
    inpaint_model: 'gemini-3-pro-image',
  });

  const [visionModel, setVisionModel] = useState(
    () => localStorage.getItem('studio_vision_model') || 'gemini-3.5-flash-lite'
  );
  const [imagenModel, setImagenModel] = useState(
    () => localStorage.getItem('studio_imagen_model') || 'gemini-3.1-flash-image'
  );

  const loadModelConfig = useCallback(async () => {
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
  }, []);

  const handleVisionModelChange = useCallback((model) => {
    setVisionModel(model);
    localStorage.setItem('studio_vision_model', model);
  }, []);

  const handleImagenModelChange = useCallback((model) => {
    setImagenModel(model);
    localStorage.setItem('studio_imagen_model', model);
  }, []);

  return {
    modelConfig,
    visionModel,
    imagenModel,
    loadModelConfig,
    handleVisionModelChange,
    handleImagenModelChange,
  };
}
