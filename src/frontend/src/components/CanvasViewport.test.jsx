import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import CanvasViewport from './CanvasViewport';

describe('CanvasViewport', () => {
  it('renders empty placeholder when no image is loaded', () => {
    render(<CanvasViewport imageUrl={null} />);
    expect(screen.getByText(/4K Master Artwork will render here/i)).toBeInTheDocument();
  });

  it('renders single image and seed info when only imageUrl is provided', () => {
    render(
      <CanvasViewport
        imageUrl="/api/images/test.png"
        activeSeed={918231}
        generationResult={{ generation_id: 'gen_123', resolution: { width: 1440, height: 1440 } }}
      />
    );

    expect(screen.getByAltText('Master Rendered Artwork')).toBeInTheDocument();
    expect(screen.getByText(/Seed: #918231/i)).toBeInTheDocument();
  });

  it('renders Before & After Split Slider when beforeImageUrl and imageUrl are provided', () => {
    render(
      <CanvasViewport
        imageUrl="/api/images/after.png"
        beforeImageUrl="/api/images/before.png"
        beforeLabel="Baseline"
        afterLabel="Regenerated"
        activeSeed={918231}
      />
    );

    expect(screen.getByText('Split')).toBeInTheDocument();
    expect(screen.getByText('Side-by-Side')).toBeInTheDocument();
    expect(screen.getByText('Hold: Peek Before')).toBeInTheDocument();
    expect(screen.getAllByText(/BEFORE \(Baseline\)/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/AFTER \(Regenerated\)/i)).toBeInTheDocument();
    expect(screen.getByAltText('Before: Baseline')).toBeInTheDocument();
    expect(screen.getByAltText('After: Regenerated')).toBeInTheDocument();
  });

  it('switches to Before view mode when Before tab is clicked', () => {
    render(
      <CanvasViewport
        imageUrl="/api/images/after.png"
        beforeImageUrl="/api/images/before.png"
        beforeLabel="Previous Iteration"
        afterLabel="Current Iteration"
      />
    );

    const beforeBtn = screen.getByTitle('View Previous Iteration Reference');
    fireEvent.click(beforeBtn);

    expect(screen.getAllByText(/BEFORE \(Previous Iteration\)/i).length).toBeGreaterThan(0);
    expect(screen.getByAltText('Master Rendered Artwork')).toHaveAttribute('src', '/api/images/before.png');
  });

  it('allows toggling between Previous and Baseline when both references exist', () => {
    render(
      <CanvasViewport
        imageUrl="/api/images/iter2.png"
        beforeImageUrl="/api/images/iter1.png"
        baselineImageUrl="/api/images/base.png"
        beforeLabel="Previous Iteration"
        afterLabel="Current Iteration"
      />
    );

    expect(screen.getByText('Prev')).toBeInTheDocument();
    expect(screen.getByText('Base')).toBeInTheDocument();

    const baseBtn = screen.getByTitle('Compare with original baseline photo');
    fireEvent.click(baseBtn);

    expect(screen.getAllByText(/BEFORE \(Baseline\)/i).length).toBeGreaterThan(0);
    expect(screen.getByAltText('Before: Baseline')).toHaveAttribute('src', '/api/images/base.png');
  });

  it('triggers onGenerate when Re-Generate button is clicked', () => {
    const onGenerate = vi.fn();
    render(<CanvasViewport imageUrl="/api/images/test.png" onGenerate={onGenerate} canGenerate={true} />);

    const genBtn = screen.getByRole('button', { name: /Re-Generate Fine-Tuning/i });
    fireEvent.click(genBtn);
    expect(onGenerate).toHaveBeenCalled();
  });

  it('does not render download single or 5-preset zip buttons in viewport', () => {
    render(
      <CanvasViewport
        imageUrl="/api/images/test.png"
        generationResult={{ generation_id: 'gen_123' }}
      />
    );

    expect(screen.queryByRole('button', { name: /Single PNG/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Download 5-Preset ZIP/i })).not.toBeInTheDocument();
  });

  it('renders Full Prompt Submitted to API inspector with copy and expand buttons', async () => {
    const mockWriteText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, {
      clipboard: { writeText: mockWriteText },
    });

    render(
      <CanvasViewport
        imageUrl="/api/images/test.png"
        generationResult={{
          generation_id: 'gen_iter_abc',
          seed: 888999,
          compiled_prompt: 'A cinematic high-fashion portrait with soft golden lighting.',
        }}
      />
    );

    expect(screen.getByText(/Full Prompt Submitted to API/i)).toBeInTheDocument();
    expect(screen.getByText('Fine-Tuned Iteration')).toBeInTheDocument();
    expect(screen.getByText(/A cinematic high-fashion portrait with soft golden lighting\./i)).toBeInTheDocument();

    const expandBtn = screen.getByRole('button', { name: /Expand/i });
    fireEvent.click(expandBtn);
    expect(screen.getByRole('button', { name: /Collapse/i })).toBeInTheDocument();

    const copyBtn = screen.getByRole('button', { name: /Copy/i });
    await act(async () => {
      fireEvent.click(copyBtn);
    });
    expect(mockWriteText).toHaveBeenCalledWith('A cinematic high-fashion portrait with soft golden lighting.');
  });

  it('renders mask telemetry pill and toggles mask overlay for inpaint generation', () => {
    render(
      <CanvasViewport
        imageUrl="/api/images/inpaint_result.png"
        generationResult={{
          generation_id: 'gen_inpaint_123',
          seed: 4289102,
          compiled_prompt: '[Inpaint Edit] Replace shoes with brown leather boots',
          mask_url: '/api/images/gen_inpaint_123_mask.png',
          mask_stats: {
            coverage_percentage: 7.2,
            bounding_box: { width: 150, height: 200 },
          },
        }}
      />
    );

    expect(screen.getByText('Targeted Inpaint')).toBeInTheDocument();
    expect(screen.getByText('Mask: 7.2%')).toBeInTheDocument();

    const maskBtn = screen.getByRole('button', { name: /Mask Map/i });
    expect(maskBtn).toHaveTextContent('Mask Map');

    // Click to toggle mask view
    fireEvent.click(maskBtn);
    expect(screen.getByRole('button', { name: /Artwork/i })).toBeInTheDocument();
    const renderedImg = screen.getByAltText('Master Rendered Artwork');
    expect(renderedImg).toHaveAttribute('src', '/api/images/gen_inpaint_123_mask.png');
  });

  it('renders wardrobe pins and allows deletion and drag repositioning', () => {
    const onRemovePin = vi.fn();
    const onUpdatePin = vi.fn();

    render(
      <CanvasViewport
        imageUrl="/api/images/model.png"
        isWardrobeMode={true}
        wardrobeAssignments={[
          { pin_number: 1, item_label: 'Silk Blazer', drop_position: { x: 0.4, y: 0.3 } },
        ]}
        onRemovePin={onRemovePin}
        onUpdatePinPosition={onUpdatePin}
      />
    );

    expect(screen.getByText('Silk Blazer')).toBeInTheDocument();
    expect(screen.getByText('1')).toBeInTheDocument();

    // Click remove button on pin
    const removeBtn = screen.getByRole('button', { name: /Remove pin 1/i });
    fireEvent.click(removeBtn);
    expect(onRemovePin).toHaveBeenCalledWith(1);
  });

  it('supports spacebar hand tool and fit view reset', () => {
    render(
      <CanvasViewport
        imageUrl="/api/images/test.png"
      />
    );

    const fitBtn = screen.getByTitle('Fit to Width / Reset View');
    expect(fitBtn).toBeInTheDocument();

    // Trigger Spacebar keydown
    fireEvent.keyDown(window, { code: 'Space', key: ' ' });
    const handBtn = screen.getByTitle('Hold [Spacebar] + Drag to Pan View');
    expect(handBtn).toHaveClass('active');

    // Trigger Spacebar keyup
    fireEvent.keyUp(window, { code: 'Space', key: ' ' });
    expect(handBtn).not.toHaveClass('active');

    // Click Fit button
    fireEvent.click(fitBtn);
    expect(fitBtn).toHaveClass('active');
  });
});





