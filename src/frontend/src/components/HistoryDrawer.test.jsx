import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import HistoryDrawer from './HistoryDrawer';

describe('HistoryDrawer', () => {
  const mockHistory = [
    {
      id: 'gen_1',
      is_baseline: true,
      seed: 111,
      master_image_url: '/api/images/gen_1.png',
      compiled_prompt: 'root baseline prompt',
      created_at: '2026-08-24T00:00:00Z',
    },
    {
      id: 'gen_2',
      is_baseline: false,
      seed: 111,
      master_image_url: '/api/images/gen_2.png',
      compiled_prompt: 'fine-tuned child iteration',
      created_at: '2026-08-24T00:05:00Z',
    },
  ];

  it('renders history items with baseline and iteration badges', () => {
    render(
      <HistoryDrawer
        isOpen={true}
        history={mockHistory}
        activeGenerationId="gen_2"
        onClose={() => {}}
      />
    );

    expect(screen.getByText(/Generation Lineage & History/i)).toBeInTheDocument();
    expect(screen.getByText('Baseline')).toBeInTheDocument();
    expect(screen.getByText('Iteration')).toBeInTheDocument();
    expect(screen.getByText(/root baseline prompt/i)).toBeInTheDocument();
  });

  it('triggers onRestoreGeneration when restore button is clicked', () => {
    const onRestore = vi.fn();
    render(
      <HistoryDrawer
        isOpen={true}
        history={mockHistory}
        activeGenerationId="gen_2"
        onRestoreGeneration={onRestore}
        onClose={() => {}}
      />
    );

    const restoreBtns = screen.getAllByRole('button', { name: /Restore State/i });
    fireEvent.click(restoreBtns[0]);
    expect(onRestore).toHaveBeenCalledWith(mockHistory[0]);
  });

  it('handles compare selection toggle', () => {
    const onToggleCompare = vi.fn();
    render(
      <HistoryDrawer
        isOpen={true}
        history={mockHistory}
        selectedForCompare={['gen_1']}
        onToggleCompare={onToggleCompare}
        onClose={() => {}}
      />
    );

    const checkboxes = screen.getAllByRole('checkbox');
    fireEvent.click(checkboxes[1]);
    expect(onToggleCompare).toHaveBeenCalledWith('gen_2');
  });

  it('supports copying and expanding full prompt on history cards', async () => {
    const mockWriteText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, {
      clipboard: { writeText: mockWriteText },
    });

    render(
      <HistoryDrawer
        isOpen={true}
        history={mockHistory}
        activeGenerationId="gen_1"
        onClose={() => {}}
      />
    );

    const copyBtns = screen.getAllByRole('button', { name: /Copy Prompt/i });
    await act(async () => {
      fireEvent.click(copyBtns[0]);
    });
    expect(mockWriteText).toHaveBeenCalledWith('root baseline prompt');

    const expandBtns = screen.getAllByRole('button', { name: /Full Prompt/i });
    fireEvent.click(expandBtns[0]);
    expect(screen.getByRole('button', { name: /Less/i })).toBeInTheDocument();
  });

  it('renders inpaint mask badge and toggles mask thumbnail preview', () => {
    const inpaintHistory = [
      {
        id: 'gen_inpaint_99',
        is_baseline: false,
        seed: 777,
        master_image_url: '/api/images/gen_inpaint_99_master.png',
        mask_image_url: '/api/images/gen_inpaint_99_mask.png',
        inpaint_metadata: {
          mask_url: '/api/images/gen_inpaint_99_mask.png',
          mask_stats: { coverage_percentage: 6.5 },
        },
        compiled_prompt: '[Inpaint Edit] change hair to emerald',
        created_at: '2026-08-24T00:10:00Z',
      },
    ];

    render(
      <HistoryDrawer
        isOpen={true}
        history={inpaintHistory}
        activeGenerationId="gen_inpaint_99"
        onClose={() => {}}
      />
    );

    expect(screen.getByText(/Inpaint \(6.5%\)/i)).toBeInTheDocument();
    expect(screen.getByText(/Area: 6.5%/i)).toBeInTheDocument();

    const showMaskBtn = screen.getByRole('button', { name: /Show Mask/i });
    expect(showMaskBtn).toHaveTextContent('Show Mask');

    // Clicking toggles to Show Image and changes image src
    fireEvent.click(showMaskBtn);
    expect(screen.getByRole('button', { name: /Show Image/i })).toBeInTheDocument();
    const img = screen.getByRole('img', { name: /Mask for gen_inpaint_99/i });
    expect(img).toHaveAttribute('src', '/api/images/gen_inpaint_99_mask.png');
  });
});


