import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import React from 'react';
import TagStudio from './TagStudio';
import { DEFAULT_TAG_STATE } from '../utils/defaultTags';

describe('TagStudio component', () => {
  it('renders studio section headers and 9 granular categories', () => {
    render(
      <TagStudio
        tagState={DEFAULT_TAG_STATE}
        onUpdateTagState={vi.fn()}
        lockedCategories={[]}
        onToggleCategoryLock={vi.fn()}
      />
    );

    expect(screen.getByText(/Macro Studio \(Visual Levers & Prompt Compiler\)/i)).toBeInTheDocument();
    expect(screen.getByText(/Subject & Character Details/i)).toBeInTheDocument();
    expect(screen.getByText(/Environment & Setting/i)).toBeInTheDocument();
    expect(screen.getByText(/Wardrobe & Hairstyle/i)).toBeInTheDocument();
    expect(screen.getByText(/Lighting & Atmosphere/i)).toBeInTheDocument();
    expect(screen.getByText(/Camera & Optical Specs/i)).toBeInTheDocument();
    expect(screen.getByText(/Live Compiled Prompt/i)).toBeInTheDocument();
  });

  it('allows adding a custom tag to a category', () => {
    const handleUpdate = vi.fn();
    render(
      <TagStudio
        tagState={DEFAULT_TAG_STATE}
        onUpdateTagState={handleUpdate}
        lockedCategories={[]}
        onToggleCategoryLock={vi.fn()}
      />
    );

    const input = screen.getByPlaceholderText(/\+ Add tag to Subject & Character Details/i);
    fireEvent.change(input, { target: { value: 'hazel brown eyes' } });
    fireEvent.keyDown(input, { key: 'Enter' });

    expect(handleUpdate).toHaveBeenCalled();
  });

  it('triggers category lock toggle when lock button clicked', () => {
    const handleToggleLock = vi.fn();
    render(
      <TagStudio
        tagState={DEFAULT_TAG_STATE}
        onUpdateTagState={vi.fn()}
        lockedCategories={['camera_optics']}
        onToggleCategoryLock={handleToggleLock}
      />
    );

    const lockBtn = screen.getByRole('button', { name: /Unlock Camera & Optical Specs/i });
    fireEvent.click(lockBtn);

    expect(handleToggleLock).toHaveBeenCalledWith('camera_optics');
  });

  it('displays Modified indicator and allows reset to baseline', () => {
    const handleReset = vi.fn();
    const baselineSnapshot = {
      categories: {
        ...DEFAULT_TAG_STATE.categories,
        subject_details: [{ id: 's1', label: 'original model', enabled: true, locked: false, isCustom: false }],
      },
    };
    const modifiedState = {
      categories: {
        ...DEFAULT_TAG_STATE.categories,
        subject_details: [{ id: 's1', label: 'modified model', enabled: true, locked: false, isCustom: false }],
      },
    };

    render(
      <TagStudio
        tagState={modifiedState}
        onUpdateTagState={vi.fn()}
        lockedCategories={[]}
        onToggleCategoryLock={vi.fn()}
        baselineTagSnapshot={baselineSnapshot}
        useImageReference={true}
        onToggleImageReference={vi.fn()}
        onResetToBaseline={handleReset}
      />
    );

    expect(screen.getByText('Modified')).toBeInTheDocument();
    const resetBtn = screen.getByRole('button', { name: /Reset to Base/i });
    expect(resetBtn).toBeInTheDocument();
    fireEvent.click(resetBtn);
    expect(handleReset).toHaveBeenCalled();
  });
});

