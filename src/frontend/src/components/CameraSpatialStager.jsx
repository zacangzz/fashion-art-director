import React, { useRef, useState, useCallback, useEffect } from 'react';
import {
  Camera,
  User,
  Compass,
  Maximize2,
  Sliders,
  Move,
  Eye,
  Sun,
  Grid,
} from 'lucide-react';
import Badge from './ui/Badge';

/**
 * Interactive 2D/3D Camera & Subject Spatial Stager.
 * Allows art directors to drag the Subject Position and Camera Vantage Point / FOV Cone
 * over the background reference image to direct 3D scene re-projection.
 */
export default function CameraSpatialStager({
  backgroundImageUrl,
  stagingParams = {},
  onChange,
}) {
  const containerRef = useRef(null);
  const [activeDragTarget, setActiveDragTarget] = useState(null); // 'subject' | 'camera' | null
  const [showGrid, setShowGrid] = useState(true);

  // Normalized coordinates (0.0 to 1.0)
  const subjectX = stagingParams.subject_x ?? 0.5;
  const subjectY = stagingParams.subject_y ?? 0.65;
  const cameraX = stagingParams.camera_x ?? 0.5;
  const cameraY = stagingParams.camera_y ?? 0.9;
  const cameraAngle = stagingParams.camera_angle ?? 'facing_window';
  const focalLength = stagingParams.focal_length_mm ?? 35;
  const zoomLevel = stagingParams.zoom_level ?? 'environmental';

  // Calculate dynamic FOV cone angle based on focal length
  // 24mm = wide ~84deg, 35mm = 63deg, 50mm = 46deg, 85mm = 28deg
  const fovDegrees = Math.max(24, Math.min(90, Math.round(2000 / focalLength)));

  // Calculate angle between camera and subject in degrees
  const dx = (subjectX - cameraX) * 100;
  const dy = (subjectY - cameraY) * 100;
  const pointingAngleRad = Math.atan2(dy, dx);
  const pointingAngleDeg = (pointingAngleRad * 180) / Math.PI + 90;

  // Handle Dragging
  const handlePointerDown = (target, e) => {
    e.stopPropagation();
    setActiveDragTarget(target);
  };

  const handlePointerMove = useCallback(
    (e) => {
      if (!activeDragTarget || !containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      if (!rect.width || !rect.height) return;

      const clientX = e.clientX ?? e.touches?.[0]?.clientX;
      const clientY = e.clientY ?? e.touches?.[0]?.clientY;
      if (clientX === undefined || clientY === undefined) return;

      // Clamped normalized coordinates with margin
      const rawX = (clientX - rect.left) / rect.width;
      const rawY = (clientY - rect.top) / rect.height;
      const clampedX = Math.max(0.08, Math.min(0.92, rawX));
      const clampedY = Math.max(0.08, Math.min(0.92, rawY));

      if (activeDragTarget === 'subject') {
        onChange?.({
          ...stagingParams,
          subject_x: Number(clampedX.toFixed(3)),
          subject_y: Number(clampedY.toFixed(3)),
        });
      } else if (activeDragTarget === 'camera') {
        onChange?.({
          ...stagingParams,
          camera_x: Number(clampedX.toFixed(3)),
          camera_y: Number(clampedY.toFixed(3)),
        });
      }
    },
    [activeDragTarget, onChange, stagingParams]
  );

  const handlePointerUp = useCallback(() => {
    setActiveDragTarget(null);
  }, []);

  useEffect(() => {
    if (activeDragTarget) {
      window.addEventListener('pointermove', handlePointerMove);
      window.addEventListener('pointerup', handlePointerUp);
      window.addEventListener('touchmove', handlePointerMove, { passive: false });
      window.addEventListener('touchend', handlePointerUp);
      return () => {
        window.removeEventListener('pointermove', handlePointerMove);
        window.removeEventListener('pointerup', handlePointerUp);
        window.removeEventListener('touchmove', handlePointerMove);
        window.removeEventListener('touchend', handlePointerUp);
      };
    }
  }, [activeDragTarget, handlePointerMove, handlePointerUp]);

  const handleFocalLengthChange = (e) => {
    const val = Number(e.target.value);
    let level = 'standard';
    if (val <= 28) level = 'wide';
    else if (val <= 40) level = 'environmental';
    else if (val <= 60) level = 'standard';
    else level = 'portrait_close';

    onChange?.({
      ...stagingParams,
      focal_length_mm: val,
      zoom_level: level,
    });
  };

  const handleAnglePreset = (angleId) => {
    onChange?.({
      ...stagingParams,
      camera_angle: angleId,
    });
  };

  // Human-readable summary
  const getSubjectPositionText = () => {
    const horizontal = subjectX < 0.35 ? 'Left' : subjectX > 0.65 ? 'Right' : 'Center';
    const vertical = subjectY < 0.4 ? 'Deep Background' : subjectY < 0.7 ? 'Midground' : 'Foreground';
    return `${horizontal} ${vertical}`;
  };

  const getCameraVantageText = () => {
    const presets = {
      facing_window: 'Facing Window (Backlit)',
      facing_camera: 'Facing Camera',
      low_angle: 'Low Angle Hero',
      high_angle: 'High Angle Overhead',
      profile_angle: 'Profile 3/4 Angle',
    };
    return presets[cameraAngle] || cameraAngle;
  };

  return (
    <div className="camera-spatial-stager" role="region" aria-label="3D Camera & Subject Spatial Stager">
      {/* Header & Controls */}
      <div className="stager-header">
        <div className="stager-title-group">
          <Compass size={13} className="text-emerald-400" />
          <span className="stager-title">Spatial Camera & Subject Stager</span>
        </div>
        <button
          type="button"
          className={`stager-grid-toggle ${showGrid ? 'active' : ''}`}
          onClick={() => setShowGrid((prev) => !prev)}
          title="Toggle Perspective 3D Grid Overlay"
          aria-label="Toggle 3D Grid"
        >
          <Grid size={12} />
          <span>3D Grid</span>
        </button>
      </div>

      {/* Interactive Staging Viewport */}
      <div
        ref={containerRef}
        className="stager-canvas-wrap"
        tabIndex={0}
        aria-label="Spatial Stage Canvas: Drag Subject and Camera pins to reposition"
      >
        {backgroundImageUrl ? (
          <img
            src={backgroundImageUrl}
            alt="Reference Environment Background"
            className="stager-bg-image"
          />
        ) : (
          <div className="stager-bg-placeholder">Reference Environment</div>
        )}

        {/* 3D Perspective Grid Overlay */}
        {showGrid && (
          <div className="stager-grid-overlay" aria-hidden="true">
            <div className="grid-horizon-line" />
            <div className="grid-vanishing-point" />
          </div>
        )}

        {/* SVG Field of View (FOV) Camera Cone */}
        <svg className="stager-fov-svg" aria-hidden="true">
          <defs>
            <radialGradient id="fovGrad" cx="0%" cy="0%" r="100%">
              <stop offset="0%" stopColor="rgba(6, 182, 212, 0.45)" />
              <stop offset="70%" stopColor="rgba(6, 182, 212, 0.12)" />
              <stop offset="100%" stopColor="rgba(6, 182, 212, 0.0)" />
            </radialGradient>
          </defs>
          <line
            x1={`${cameraX * 100}%`}
            y1={`${cameraY * 100}%`}
            x2={`${subjectX * 100}%`}
            y2={`${subjectY * 100}%`}
            stroke="rgba(6, 182, 212, 0.6)"
            strokeWidth="1.5"
            strokeDasharray="3 3"
          />
        </svg>

        {/* 1. Draggable Subject Pin */}
        <div
          className={`stager-pin stager-subject-pin ${activeDragTarget === 'subject' ? 'is-dragging' : ''}`}
          style={{
            left: `${subjectX * 100}%`,
            top: `${subjectY * 100}%`,
          }}
          onPointerDown={(e) => handlePointerDown('subject', e)}
          role="button"
          tabIndex={0}
          aria-label={`Subject Pin: Positioned at ${getSubjectPositionText()}. Drag to reposition.`}
        >
          <div className="pin-halo subject-halo" />
          <div className="pin-body subject-body">
            <User size={13} className="pin-icon" />
          </div>
          <span className="pin-label">Subject</span>
        </div>

        {/* 2. Draggable Camera Pin & FOV Indicator */}
        <div
          className={`stager-pin stager-camera-pin ${activeDragTarget === 'camera' ? 'is-dragging' : ''}`}
          style={{
            left: `${cameraX * 100}%`,
            top: `${cameraY * 100}%`,
          }}
          onPointerDown={(e) => handlePointerDown('camera', e)}
          role="button"
          tabIndex={0}
          aria-label={`Camera Pin: Vantage angle ${getCameraVantageText()}. Drag to reposition.`}
        >
          <div className="pin-halo camera-halo" />
          <div
            className="pin-body camera-body"
            style={{ transform: `rotate(${pointingAngleDeg}deg)` }}
          >
            <Camera size={13} className="pin-icon" />
            <div className="camera-lens-tip" />
          </div>
          <span className="pin-label">Camera ({focalLength}mm)</span>
        </div>
      </div>

      {/* Lens Focal Length / Zoom Slider */}
      <div className="stager-lens-section">
        <div className="stager-slider-header">
          <span className="stager-section-title">
            <Maximize2 size={11} className="text-cyan-400" />
            Lens Focal Length / Framing:
          </span>
          <span className="stager-lens-badge">{focalLength}mm • {zoomLevel.replace('_', ' ').toUpperCase()}</span>
        </div>
        <input
          type="range"
          min={24}
          max={85}
          step={1}
          value={focalLength}
          onChange={handleFocalLengthChange}
          className="slider-input stager-focal-slider"
          aria-label="Lens Focal Length in millimeters"
        />
        <div className="stager-lens-scale">
          <span>24mm (Wide / Zoom Out)</span>
          <span>35mm (Env)</span>
          <span>50mm (Std)</span>
          <span>85mm (Portrait)</span>
        </div>
      </div>

      {/* Camera Vantage Presets */}
      <div className="stager-angle-presets">
        <span className="stager-section-title">
          <Eye size={11} className="text-amber-400" />
          Camera Viewpoint Presets:
        </span>
        <div className="stager-chip-group">
          {[
            { id: 'facing_window', label: '🪟 Facing Window (Backlit)' },
            { id: 'facing_camera', label: '📸 Facing Subject Frontal' },
            { id: 'low_angle', label: '📐 Low Angle Hero' },
            { id: 'high_angle', label: '📐 High Angle Pitch' },
            { id: 'profile_angle', label: '👥 Profile 3/4 Angle' },
          ].map((preset) => (
            <button
              key={preset.id}
              type="button"
              className={`stager-preset-chip ${cameraAngle === preset.id ? 'active' : ''}`}
              onClick={() => handleAnglePreset(preset.id)}
            >
              {preset.label}
            </button>
          ))}
        </div>
      </div>

      {/* Live Readout Pill */}
      <div className="stager-summary-pill" role="status" aria-live="polite">
        <div className="stager-summary-dot" />
        <span>
          <strong>Live Staging:</strong> {focalLength}mm {zoomLevel} lens • {getCameraVantageText()} • Subject at {getSubjectPositionText()}
        </span>
      </div>
    </div>
  );
}
