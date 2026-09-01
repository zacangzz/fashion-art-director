import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import CameraSpatialStagerModal from './CameraSpatialStagerModal';

describe('CameraSpatialStagerModal Component', () => {
  const sampleStaging = {
    subject_x: 0.5,
    subject_y: 0.65,
    camera_x: 0.5,
    camera_y: 0.9,
    camera_angle: 'facing_window',
    focal_length_mm: 35,
    zoom_level: 'environmental',
  };

  it('renders interactive staging popup modal when isOpen is true', () => {
    render(
      <CameraSpatialStagerModal
        isOpen={true}
        onClose={vi.fn()}
        backgroundImageUrl="https://example.com/window_room.png"
        stagingParams={sampleStaging}
        onChange={vi.fn()}
      />
    );

    expect(screen.getByText('Spatial Camera & Subject Stager')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Subject Pin/i })).toBeInTheDocument();
    expect(screen.getByText(/Camera \(35mm\)/i)).toBeInTheDocument();
    expect(screen.getByRole('img', { name: /Reference Environment Background/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Apply 3D Staging/i })).toBeInTheDocument();
  });

  it('calls onChange when adjusting the lens focal length slider inside modal', () => {
    const handleChange = vi.fn();
    render(
      <CameraSpatialStagerModal
        isOpen={true}
        onClose={vi.fn()}
        backgroundImageUrl="https://example.com/window_room.png"
        stagingParams={sampleStaging}
        onChange={handleChange}
      />
    );

    const slider = screen.getByLabelText(/Lens Focal Length in millimeters/i);
    fireEvent.change(slider, { target: { value: '24' } });

    expect(handleChange).toHaveBeenCalledWith(
      expect.objectContaining({
        focal_length_mm: 24,
        zoom_level: 'wide',
      })
    );
  });

  it('calls onChange when clicking a camera viewpoint preset chip', () => {
    const handleChange = vi.fn();
    render(
      <CameraSpatialStagerModal
        isOpen={true}
        onClose={vi.fn()}
        backgroundImageUrl="https://example.com/window_room.png"
        stagingParams={sampleStaging}
        onChange={handleChange}
      />
    );

    const presetChip = screen.getByText(/Low Angle Hero/i);
    fireEvent.click(presetChip);

    expect(handleChange).toHaveBeenCalledWith(
      expect.objectContaining({
        camera_angle: 'low_angle',
      })
    );
  });

  it('calls onDepthOfFieldChange and onLightingModeChange when selecting optical chips', () => {
    const handleDof = vi.fn();
    const handleLighting = vi.fn();

    render(
      <CameraSpatialStagerModal
        isOpen={true}
        onClose={vi.fn()}
        backgroundImageUrl="https://example.com/window_room.png"
        stagingParams={sampleStaging}
        onChange={vi.fn()}
        depthOfField="natural"
        onDepthOfFieldChange={handleDof}
        lightingMode="harmonize_ambient"
        onLightingModeChange={handleLighting}
      />
    );

    const bokehChip = screen.getByText(/Cinematic Bokeh/i);
    fireEvent.click(bokehChip);
    expect(handleDof).toHaveBeenCalledWith('cinematic_bokeh');

    const whiteBalChip = screen.getByText(/Calibrated White Balance/i);
    fireEvent.click(whiteBalChip);
    expect(handleLighting).toHaveBeenCalledWith('match_white_balance');
  });

  it('calls onClose when clicking Apply 3D Staging button', () => {
    const handleClose = vi.fn();
    render(
      <CameraSpatialStagerModal
        isOpen={true}
        onClose={handleClose}
        backgroundImageUrl="https://example.com/window_room.png"
        stagingParams={sampleStaging}
        onChange={vi.fn()}
      />
    );

    const applyBtn = screen.getByRole('button', { name: /Apply 3D Staging/i });
    fireEvent.click(applyBtn);
    expect(handleClose).toHaveBeenCalledOnce();
  });

  it('toggles 3D perspective grid overlay on button click', () => {
    render(
      <CameraSpatialStagerModal
        isOpen={true}
        onClose={vi.fn()}
        backgroundImageUrl="https://example.com/window_room.png"
        stagingParams={sampleStaging}
        onChange={vi.fn()}
      />
    );

    const gridToggle = screen.getByRole('button', { name: /Toggle 3D Grid/i });
    expect(gridToggle).toHaveClass('active');

    fireEvent.click(gridToggle);
    expect(gridToggle).not.toHaveClass('active');
  });
});
