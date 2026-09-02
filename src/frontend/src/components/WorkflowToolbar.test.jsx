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
});
