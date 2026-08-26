import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import WardrobePanel from './WardrobePanel';

describe('WardrobePanel Component', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        items: [
          {
            id: 'wd_1',
            label: 'Wool Trench Coat',
            category: 'outerwear',
            image_url: '/api/wardrobe/items/wd_1/image',
          },
          {
            id: 'wd_2',
            label: 'White Cotton Shirt',
            category: 'tops',
            image_url: '/api/wardrobe/items/wd_2/image',
          },
        ],
      }),
    }));
  });

  it('renders Wardrobe Studio panel with title and upload dropzone', async () => {
    render(<WardrobePanel isOpen={true} onClose={vi.fn()} />);

    expect(screen.getByText('Wardrobe Studio')).toBeInTheDocument();
    expect(screen.getByText(/Upload Garment Sheet \/ Lookbook/i)).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('Wool Trench Coat')).toBeInTheDocument();
      expect(screen.getByText('White Cotton Shirt')).toBeInTheDocument();
    });
  });

  it('renders queued pin assignments and triggers compose', async () => {
    const mockCompose = vi.fn();
    const assignments = [
      {
        wardrobe_item_id: 'wd_1',
        pin_number: 1,
        item_label: 'Wool Trench Coat',
        drop_position: { x: 0.5, y: 0.3 },
      },
    ];

    render(
      <WardrobePanel
        isOpen={true}
        onClose={vi.fn()}
        assignments={assignments}
        onCompose={mockCompose}
        activeGenerationId="gen_test"
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Queued Swaps (1)')).toBeInTheDocument();
    });

    const composeBtn = screen.getByRole('button', { name: /Compose Swaps \(1 item\)/i });
    expect(composeBtn).toBeEnabled();
    fireEvent.click(composeBtn);

    expect(mockCompose).toHaveBeenCalled();
  });

  it('renders Delete All button and calls delete endpoint when confirmed', async () => {
    vi.spyOn(window, 'confirm').mockImplementation(() => true);
    render(<WardrobePanel isOpen={true} onClose={vi.fn()} onClearAssignments={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText('Wool Trench Coat')).toBeInTheDocument();
    });

    const deleteAllBtn = screen.getByRole('button', { name: /Delete All/i });
    expect(deleteAllBtn).toBeInTheDocument();

    fireEvent.click(deleteAllBtn);

    await waitFor(() => {
      expect(window.fetch).toHaveBeenCalledWith('/api/wardrobe/items', {
        method: 'DELETE',
      });
    });
  });

  it('returns null when isOpen is false', () => {
    const { container } = render(<WardrobePanel isOpen={false} />);
    expect(container.firstChild).toBeNull();
  });
});

