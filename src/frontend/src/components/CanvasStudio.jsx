import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  Paintbrush,
  Eraser,
  Trash2,
  Wand2,
  Loader2,
  ArrowLeft,
  History,
  Info,
  Sliders,
  Sparkles,
  CheckCircle2,
  Eye,
  EyeOff,
} from 'lucide-react';
import { inpaintRegion } from '../services/apiClient';

export default function CanvasStudio({
  imageUrl = null,
  generationId = null,
  activeSeed = 4289102,
  onEditComplete,
  onSwitchToGraph,
  onOpenHistory,
  isInpainting = false,
  setIsInpainting,
}) {
  const [activeTool, setActiveTool] = useState('brush'); // 'brush' | 'eraser'
  const [brushSize, setBrushSize] = useState(25);
  const [prompt, setPrompt] = useState('');
  const [errorMessage, setErrorMessage] = useState(null);
  const [showTips, setShowTips] = useState(false);
  const [hasMaskDrawn, setHasMaskDrawn] = useState(false);
  const [isMaskVisible, setIsMaskVisible] = useState(true);

  const containerRef = useRef(null);
  const bgCanvasRef = useRef(null);
  const maskCanvasRef = useRef(null);
  const isDrawingRef = useRef(false);
  const lastPointRef = useRef(null);
  const imageObjRef = useRef(null);

  // Load and render background image onto canvas
  useEffect(() => {
    if (!imageUrl) return;

    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => {
      imageObjRef.current = img;
      const width = img.naturalWidth || 1080;
      const height = img.naturalHeight || 1620;

      const bgCanvas = bgCanvasRef.current;
      const maskCanvas = maskCanvasRef.current;

      if (bgCanvas && maskCanvas) {
        bgCanvas.width = width;
        bgCanvas.height = height;
        maskCanvas.width = width;
        maskCanvas.height = height;

        const bgCtx = bgCanvas.getContext('2d');
        bgCtx.clearRect(0, 0, width, height);
        bgCtx.drawImage(img, 0, 0, width, height);

        // Reset mask when base image changes
        const maskCtx = maskCanvas.getContext('2d');
        maskCtx.clearRect(0, 0, width, height);
        setHasMaskDrawn(false);
      }
    };
    img.src = imageUrl;
  }, [imageUrl]);

  // Coordinate helper: maps viewport mouse client coordinates to canvas internal pixel coordinates
  const getCanvasCoords = (e) => {
    const maskCanvas = maskCanvasRef.current;
    if (!maskCanvas) return { x: 0, y: 0 };
    const rect = maskCanvas.getBoundingClientRect();
    const scaleX = maskCanvas.width / rect.width;
    const scaleY = maskCanvas.height / rect.height;
    return {
      x: (e.clientX - rect.left) * scaleX,
      y: (e.clientY - rect.top) * scaleY,
    };
  };

  // Drawing routines
  const drawStroke = (x, y, fromPoint = null) => {
    const maskCanvas = maskCanvasRef.current;
    if (!maskCanvas) return;
    const ctx = maskCanvas.getContext('2d');

    ctx.save();
    if (activeTool === 'brush') {
      ctx.globalCompositeOperation = 'source-over';
      ctx.fillStyle = 'rgba(239, 68, 68, 0.7)'; // Vibrant semi-transparent red overlay
      ctx.strokeStyle = 'rgba(239, 68, 68, 0.7)';
    } else {
      ctx.globalCompositeOperation = 'destination-out';
      ctx.fillStyle = 'rgba(0, 0, 0, 1)';
      ctx.strokeStyle = 'rgba(0, 0, 0, 1)';
    }

    ctx.lineWidth = brushSize * 2;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';

    ctx.beginPath();
    if (fromPoint) {
      ctx.moveTo(fromPoint.x, fromPoint.y);
      ctx.lineTo(x, y);
      ctx.stroke();
    } else {
      ctx.arc(x, y, brushSize, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();

    if (!hasMaskDrawn && activeTool === 'brush') {
      setHasMaskDrawn(true);
    }
  };

  const handleMouseDown = (e) => {
    if (isInpainting) return;
    isDrawingRef.current = true;
    const coords = getCanvasCoords(e);
    lastPointRef.current = coords;
    drawStroke(coords.x, coords.y);
  };

  const handleMouseMove = (e) => {
    if (!isDrawingRef.current || isInpainting) return;
    const coords = getCanvasCoords(e);
    drawStroke(coords.x, coords.y, lastPointRef.current);
    lastPointRef.current = coords;
  };

  const handleMouseUp = () => {
    isDrawingRef.current = false;
    lastPointRef.current = null;
  };

  const handleClearMask = () => {
    const maskCanvas = maskCanvasRef.current;
    if (!maskCanvas) return;
    const ctx = maskCanvas.getContext('2d');
    ctx.clearRect(0, 0, maskCanvas.width, maskCanvas.height);
    setHasMaskDrawn(false);
  };

  // Convert red mask into a high-contrast Black & White mask PNG
  const createBlackAndWhiteMaskBlob = async () => {
    const maskCanvas = maskCanvasRef.current;
    if (!maskCanvas) return null;

    const width = maskCanvas.width;
    const height = maskCanvas.height;

    // Read pixel data directly from maskCanvas where unbrushed pixels have alpha == 0
    const maskCtx = maskCanvas.getContext('2d');
    const srcImgData = maskCtx.getImageData(0, 0, width, height);
    const srcData = srcImgData.data;

    const exportCanvas = document.createElement('canvas');
    exportCanvas.width = width;
    exportCanvas.height = height;
    const exportCtx = exportCanvas.getContext('2d');
    const outImgData = exportCtx.createImageData(width, height);
    const outData = outImgData.data;

    for (let i = 0; i < srcData.length; i += 4) {
      // If user brushed this pixel (alpha > 10), make it Pure White (#FFFFFF)
      if (srcData[i + 3] > 10) {
        outData[i] = 255;     // R
        outData[i + 1] = 255; // G
        outData[i + 2] = 255; // B
        outData[i + 3] = 255; // Alpha
      } else {
        // Otherwise preserved untouched pixel -> Pure Black (#000000)
        outData[i] = 0;       // R
        outData[i + 1] = 0;   // G
        outData[i + 2] = 0;   // B
        outData[i + 3] = 255; // Alpha
      }
    }
    exportCtx.putImageData(outImgData, 0, 0);

    return new Promise((resolve) => {
      exportCanvas.toBlob((blob) => resolve(blob), 'image/png');
    });
  };


  // Get source image as Blob
  const getSourceImageBlob = async () => {
    if (!imageUrl) return null;
    const res = await fetch(imageUrl);
    return res.blob();
  };

  // Execute inpainting request
  const handleApplyEdit = async () => {
    if (!prompt.trim()) {
      setErrorMessage('Please describe the adjustment you want to apply in the prompt box.');
      return;
    }
    if (!hasMaskDrawn) {
      setErrorMessage('Please brush over the area of the image you want to change first.');
      return;
    }

    setIsInpainting(true);
    setErrorMessage(null);

    try {
      const [sourceBlob, maskBlob] = await Promise.all([
        getSourceImageBlob(),
        createBlackAndWhiteMaskBlob(),
      ]);

      if (!sourceBlob || !maskBlob) {
        throw new Error('Failed to prepare image and mask data.');
      }

      const result = await inpaintRegion({
        generationId: generationId || undefined,
        imageBlob: sourceBlob,
        maskBlob: maskBlob,
        prompt: prompt.trim(),
        seed: activeSeed,
      });

      if (onEditComplete) {
        onEditComplete(result);
      }

      // Clear mask for subsequent iterations
      handleClearMask();
      setPrompt('');
    } catch (err) {
      setErrorMessage(err.message || 'Inpaint edit failed. Please check your prompt and try again.');
    } finally {
      setIsInpainting(false);
    }
  };

  return (
    <div className="canvas-studio-panel">
      {/* Header bar */}
      <div className="canvas-studio-header">
        <div className="canvas-studio-title-group">
          <Paintbrush size={18} className="text-accent" />
          <span className="canvas-studio-title">Micro Studio (Canvas Inpaint)</span>
          <span className="canvas-studio-badge">Spatial Precision</span>
        </div>

        <div className="canvas-studio-header-actions">
          {onSwitchToGraph && (
            <button
              type="button"
              className="btn-secondary btn-sm"
              onClick={onSwitchToGraph}
              title="Return to Studio Workflow Selector"
            >
              <ArrowLeft size={14} />
              <span>Switch to Tag Studio</span>
            </button>
          )}

          {onOpenHistory && (
            <button
              type="button"
              className="btn-secondary btn-sm"
              onClick={onOpenHistory}
              title="View Generation History & Step Back"
            >
              <History size={14} />
              <span>Lineage History</span>
            </button>
          )}
        </div>
      </div>

      {/* Main Interactive Canvas Section */}
      <div className="canvas-studio-workspace">
        {/* Floating Toolbar above canvas */}
        <div className="canvas-studio-toolbar">
          <div className="tool-group">
            <button
              type="button"
              className={`tool-btn ${activeTool === 'brush' ? 'active' : ''}`}
              onClick={() => setActiveTool('brush')}
              title="Brush Tool (Draw Mask)"
            >
              <Paintbrush size={16} />
              <span>Brush</span>
            </button>
            <button
              type="button"
              className={`tool-btn ${activeTool === 'eraser' ? 'active' : ''}`}
              onClick={() => setActiveTool('eraser')}
              title="Eraser Tool (Remove Mask)"
            >
              <Eraser size={16} />
              <span>Eraser</span>
            </button>
          </div>

          <div className="slider-group">
            <Sliders size={14} className="text-muted" />
            <span className="slider-label">Size:</span>
            <input
              type="range"
              min="5"
              max="80"
              value={brushSize}
              onChange={(e) => setBrushSize(Number(e.target.value))}
              className="brush-size-slider"
            />
            <span className="slider-value">{brushSize}px</span>
          </div>

          <div className="tool-group-right">
            <button
              type="button"
              className={`tool-btn-secondary ${!isMaskVisible ? 'active' : ''}`}
              onClick={() => setIsMaskVisible(!isMaskVisible)}
              title={isMaskVisible ? 'Hide Mask Overlay' : 'Show Mask Overlay'}
            >
              {isMaskVisible ? <Eye size={14} /> : <EyeOff size={14} />}
              <span>{isMaskVisible ? 'Mask On' : 'Mask Off'}</span>
            </button>

            <button
              type="button"
              className="tool-btn-danger"
              onClick={handleClearMask}
              disabled={!hasMaskDrawn || isInpainting}
              title="Clear all painted mask strokes"
            >
              <Trash2 size={14} />
              <span>Clear Mask</span>
            </button>
          </div>
        </div>

        {/* Dual Stacked Canvases */}
        <div className="canvas-stage-wrapper" ref={containerRef}>
          {imageUrl ? (
            <div className="canvas-stack-container">
              <canvas ref={bgCanvasRef} className="canvas-layer canvas-layer-bg" />
              <canvas
                ref={maskCanvasRef}
                className="canvas-layer canvas-layer-mask"
                style={{ opacity: isMaskVisible ? 1 : 0 }}
                onMouseDown={handleMouseDown}
                onMouseMove={handleMouseMove}
                onMouseUp={handleMouseUp}
                onMouseLeave={handleMouseUp}
              />
            </div>
          ) : (
            <div className="canvas-stage-empty">
              <Paintbrush size={40} className="text-muted" />
              <p>No baseline image loaded. Select a baseline to start painting masks.</p>
            </div>
          )}

          {/* Inpainting Loading Indicator */}
          {isInpainting && (
            <div className="canvas-inpaint-overlay">
              <Loader2 className="spin-animation" size={40} />
              <div className="loading-title">Applying Precision Inpaint Edit...</div>
              <div className="loading-subtitle">
                Synthesizing targeted adjustment with boundary blending
              </div>
            </div>
          )}
        </div>

        {/* Prompt Input & Execution Footer */}
        <div className="canvas-studio-prompt-card">
          <div className="prompt-header-row">
            <label className="prompt-label" htmlFor="inpaint-prompt-input">
              <Sparkles size={14} className="text-accent" />
              <span>Targeted Edit Instruction</span>
            </label>
            <div className="prompt-meta-group">
              <span className="char-count">{prompt.length}/300</span>
              <button
                type="button"
                className="btn-link"
                onClick={() => setShowTips(!showTips)}
              >
                <Info size={13} />
                <span>{showTips ? 'Hide Tips' : 'Prompt Tips'}</span>
              </button>
            </div>
          </div>

          {showTips && (
            <div className="prompt-tips-callout">
              <strong>Tips for best results:</strong>
              <ul>
                <li>Focus strictly on the selected area (e.g. <em>"change the leather jacket to dark forest green suede"</em>).</li>
                <li>Specify color, texture, material, and finish for crisp adjustments.</li>
                <li>One specific change per iteration yields the cleanest preservation of the background.</li>
              </ul>
            </div>
          )}

          <div className="prompt-input-row">
            <textarea
              id="inpaint-prompt-input"
              rows={2}
              maxLength={300}
              className="canvas-prompt-textarea"
              placeholder="Describe only the change inside the painted region (e.g., 'replace with gold embroidery pattern and metallic sheen')..."
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              disabled={isInpainting}
            />
          </div>

          {errorMessage && (
            <div className="canvas-error-alert">
              <span>{errorMessage}</span>
            </div>
          )}

          <div className="prompt-actions-row">
            <div className="prompt-status-indicator">
              {hasMaskDrawn ? (
                <span className="status-badge-ready">
                  <CheckCircle2 size={13} /> Region selected
                </span>
              ) : (
                <span className="status-badge-pending">
                  Paint a mask area to enable edit
                </span>
              )}
            </div>

            <button
              type="button"
              className="btn-primary"
              disabled={!hasMaskDrawn || !prompt.trim() || isInpainting}
              onClick={handleApplyEdit}
            >
              {isInpainting ? (
                <>
                  <Loader2 className="spin-animation" size={16} />
                  <span>Applying Inpaint...</span>
                </>
              ) : (
                <>
                  <Wand2 size={16} />
                  <span>Apply Targeted Edit</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
