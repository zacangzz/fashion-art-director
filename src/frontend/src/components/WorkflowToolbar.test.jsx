import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import WorkflowToolbar from './WorkflowToolbar';

describe('WorkflowToolbar Component', () => {
  it('renders aspect ratio select with current aspect ratio', () => {
    const handleRatioChange = vi.fn();
    render(
      <WorkflowToolbar
        aspectRatio="4:5"
        onAspectRatioChange={handleRatioChange}
        activeSeed={4776950}
        seedMode="locked"
      />
    );

    const select = screen.getByLabelText(/Workflow Aspect Ratio Selection/i);
    expect(select).toBeInTheDocument();
    expect(select.value).toBe('4:5');
    expect(screen.getByText(/4K • 3072×3840/i)).toBeInTheDocument();
    expect(screen.getByText(/#4776950/i)).toBeInTheDocument();
  });

  it('triggers onAspectRatioChange callback when selection changes', () => {
    const handleRatioChange = vi.fn();
    render(
      <WorkflowToolbar
        aspectRatio="1:1"
        onAspectRatioChange={handleRatioChange}
        activeSeed={123456}
      />
    );

    const select = screen.getByLabelText(/Workflow Aspect Ratio Selection/i);
    fireEvent.change(select, { target: { value: '16:9' } });

    expect(handleRatioChange).toHaveBeenCalledWith('16:9');
  });

  it('renders seed mode toggle button when onSeedModeChange is provided', () => {
    const handleSeedModeChange = vi.fn();
    render(
      <WorkflowToolbar
        aspectRatio="1:1"
        activeSeed={999999}
        seedMode="locked"
        onSeedModeChange={handleSeedModeChange}
      />
    );

    const toggleBtn = screen.getByRole('button', { name: /Switch to Randomize Seed/i });
    expect(toggleBtn).toBeInTheDocument();
    fireEvent.click(toggleBtn);
    expect(handleSeedModeChange).toHaveBeenCalledWith('random');
  });

  it('renders Adjust Studio mode toggle and handles switching between refinement and canvas inpaint', () => {
    const handleAdjustChange = vi.fn();
    const { rerender } = render(
      <WorkflowToolbar
        showAdjustSubMode={true}
        adjustSubMode="refinement"
        onAdjustSubModeChange={handleAdjustChange}
      />
    );

    expect(screen.getByText('Adjust Studio:')).toBeInTheDocument();
    const refinementBtn = screen.getByRole('button', { name: /Refinement/i });
    const inpaintBtn = screen.getByRole('button', { name: /Canvas Inpaint/i });

    expect(refinementBtn).toBeInTheDocument();
    expect(inpaintBtn).toBeInTheDocument();
    expect(refinementBtn).toHaveClass('active');
    expect(inpaintBtn).not.toHaveClass('active');

    fireEvent.click(inpaintBtn);
    expect(handleAdjustChange).toHaveBeenCalledWith('canvas_inpaint');

    rerender(
      <WorkflowToolbar
        showAdjustSubMode={true}
        adjustSubMode="canvas_inpaint"
        onAdjustSubModeChange={handleAdjustChange}
      />
    );
    expect(inpaintBtn).toHaveClass('active');
    expect(refinementBtn).not.toHaveClass('active');

    fireEvent.click(refinementBtn);
    expect(handleAdjustChange).toHaveBeenCalledWith('refinement');
  });

  it('renders Scene Studio mode toggle and handles switching between wardrobe and props', () => {
    const handleSceneChange = vi.fn();
    render(
      <WorkflowToolbar
        showSceneSubMode={true}
        sceneSubMode="wardrobe"
        onSceneSubModeChange={handleSceneChange}
      />
    );

    expect(screen.getByText('Scene Studio:')).toBeInTheDocument();
    const wardrobeBtn = screen.getByRole('button', { name: /Wardrobe/i });
    const propsBtn = screen.getByRole('button', { name: /Props/i });

    expect(wardrobeBtn).toBeInTheDocument();
    expect(propsBtn).toBeInTheDocument();
    expect(wardrobeBtn).toHaveClass('active');

    fireEvent.click(propsBtn);
    expect(handleSceneChange).toHaveBeenCalledWith('props');
  });
});
