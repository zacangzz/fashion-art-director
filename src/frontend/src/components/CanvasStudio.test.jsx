import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import CanvasStudio from './CanvasStudio';

describe('CanvasStudio Component', () => {
  it('renders toolbar, prompt input, and action buttons', () => {
    const handleSwitch = vi.fn();
    const handleHistory = vi.fn();

    render(
      <CanvasStudio
        imageUrl="/api/images/test.png"
        generationId="gen_123"
        onSwitchToGraph={handleSwitch}
        onOpenHistory={handleHistory}
      />
    );

    expect(screen.getByText('Micro Studio (Canvas Inpaint)')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Brush/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Eraser/i })).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/Describe only the change inside the painted region/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Apply Targeted Edit/i })).toBeDisabled();
  });

  it('allows zooming in, zooming out, and resetting zoom', () => {
    render(
      <CanvasStudio
        imageUrl="/api/images/test.png"
        generationId="gen_123"
      />
    );

    const zoomInBtn = screen.getByRole('button', { name: /Zoom In/i });
    const zoomOutBtn = screen.getByRole('button', { name: /Zoom Out/i });
    const zoomResetBtn = screen.getByRole('button', { name: /Reset Zoom/i });

    expect(zoomResetBtn).toHaveTextContent('100%');

    fireEvent.click(zoomInBtn);
    expect(zoomResetBtn).toHaveTextContent('125%');

    fireEvent.click(zoomInBtn);
    expect(zoomResetBtn).toHaveTextContent('150%');

    fireEvent.click(zoomOutBtn);
    expect(zoomResetBtn).toHaveTextContent('125%');

    fireEvent.click(zoomResetBtn);
    expect(zoomResetBtn).toHaveTextContent('100%');
  });

  it('allows typing prompt and toggling tips callout', () => {
    render(
      <CanvasStudio
        imageUrl="/api/images/test.png"
        generationId="gen_123"
      />
    );

    const textarea = screen.getByPlaceholderText(/Describe only the change inside the painted region/i);
    fireEvent.change(textarea, { target: { value: 'make the coat dark green leather' } });
    expect(textarea.value).toBe('make the coat dark green leather');

    // Toggle prompt tips
    const tipsBtn = screen.getByRole('button', { name: /Prompt Tips/i });
    fireEvent.click(tipsBtn);
    expect(screen.getByText(/Tips for best results:/i)).toBeInTheDocument();
  });

  it('triggers onSwitchToGraph and onOpenHistory when header buttons clicked', () => {
    const handleSwitch = vi.fn();
    const handleHistory = vi.fn();

    render(
      <CanvasStudio
        imageUrl="/api/images/test.png"
        generationId="gen_123"
        onSwitchToGraph={handleSwitch}
        onOpenHistory={handleHistory}
      />
    );

    const switchBtn = screen.getByRole('button', { name: /Return to Studio Workflow Selector/i });
    fireEvent.click(switchBtn);
    expect(handleSwitch).toHaveBeenCalledTimes(1);

    const historyBtn = screen.getByRole('button', { name: /Lineage History/i });
    fireEvent.click(historyBtn);
    expect(handleHistory).toHaveBeenCalledTimes(1);
  });
});
