import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import WardrobePreviewModal from './WardrobePreviewModal';

describe('WardrobePreviewModal Component', () => {
  const mockItems = [
    {
      id: 'wd_01',
      label: 'Vintage Denim Jacket',
      category: 'outerwear',
      image_url: '/api/wardrobe/items/wd_01/image',
      upscaled_image_url: '/api/wardrobe/items/wd_01/upscaled-image',
      source_image_url: '/api/wardrobe/sources/lookbook_01.jpg',
      bbox: [0.1, 0.15, 0.5, 0.45],
      is_upscaled: true,
      upscale_status: 'completed',
      created_at: '2026-08-30T10:00:00Z',
      extracted_details: {
        garment_type: 'Trucker Jacket',
        fabric_texture: 'Washed raw 14oz indigo denim',
        primary_color: 'Faded Indigo',
        secondary_colors: ['Copper Rivets', 'Tobacco Stitching'],
        has_text_or_logo: true,
        exact_text_content: ['DENIM CORP', '1992'],
        logo_and_print_placement: 'Left chest pocket tag',
        has_graphic_or_print: true,
        graphic_description: 'Subtle sun-bleached fade on rear yoke',
        hardware_and_details: 'Custom embossed metal shank buttons',
      },
    },
    {
      id: 'wd_02',
      label: 'Ribbed Knit Beanie',
      category: 'accessories',
      image_url: '/api/wardrobe/items/wd_02/image',
      upscaled_image_url: null,
      is_upscaled: false,
      upscale_status: 'pending',
      created_at: '2026-08-30T10:05:00Z',
      extracted_details: {
        fabric_texture: 'Heavyweight merino wool rib knit',
        primary_color: 'Heather Charcoal',
      },
    },
  ];

  it('renders modal when open with garment specifications and quality inspector', () => {
    render(
      <WardrobePreviewModal
        isOpen={true}
        onClose={vi.fn()}
        items={mockItems}
        initialItemId="wd_01"
      />
    );

    expect(screen.getByText('Garment Quality Inspector')).toBeInTheDocument();
    expect(screen.getByText('Vintage Denim Jacket')).toBeInTheDocument();
    expect(screen.getByText('outerwear')).toBeInTheDocument();
    expect(screen.getAllByText(/4K Ultra-HD Enhanced/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Washed raw 14oz indigo denim')).toBeInTheDocument();
    expect(screen.getByText('DENIM CORP')).toBeInTheDocument();
    expect(screen.getByText(/Custom embossed metal shank buttons/i)).toBeInTheDocument();
  });

  it('switches between view modes (HD, Original Crop, Split Compare, Source Sheet)', () => {
    render(
      <WardrobePreviewModal
        isOpen={true}
        onClose={vi.fn()}
        items={mockItems}
        initialItemId="wd_01"
      />
    );

    const cropBtn = screen.getByRole('button', { name: /Original Crop/i });
    fireEvent.click(cropBtn);
    expect(cropBtn).toHaveClass('active');

    const splitBtn = screen.getByRole('button', { name: /Split Compare/i });
    fireEvent.click(splitBtn);
    expect(splitBtn).toHaveClass('active');
    expect(screen.getByLabelText(/Compare HD Enhanced versus Original Crop/i)).toBeInTheDocument();

    const sourceBtn = screen.getByRole('button', { name: /Source Sheet/i });
    fireEvent.click(sourceBtn);
    expect(sourceBtn).toHaveClass('active');
  });

  it('supports pagination next/previous to inspect other garments', () => {
    render(
      <WardrobePreviewModal
        isOpen={true}
        onClose={vi.fn()}
        items={mockItems}
        initialItemId="wd_01"
      />
    );

    expect(screen.getByText('1 / 2')).toBeInTheDocument();

    const nextBtn = screen.getByRole('button', { name: /Next garment/i });
    fireEvent.click(nextBtn);

    expect(screen.getByText('Ribbed Knit Beanie')).toBeInTheDocument();
    expect(screen.getByText('2 / 2')).toBeInTheDocument();
    expect(screen.getByText('Heavyweight merino wool rib knit')).toBeInTheDocument();
  });

  it('triggers onAddAssignment when Pin & Swap is clicked', () => {
    const handleAdd = vi.fn();
    const handleClose = vi.fn();

    render(
      <WardrobePreviewModal
        isOpen={true}
        onClose={handleClose}
        items={mockItems}
        initialItemId="wd_01"
        onAddAssignment={handleAdd}
      />
    );

    const pinBtn = screen.getByRole('button', { name: /Pin & Swap onto Subject/i });
    fireEvent.click(pinBtn);

    expect(handleAdd).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'wd_01', label: 'Vintage Denim Jacket' }),
      { x: 0.5, y: 0.5 }
    );
    expect(handleClose).toHaveBeenCalled();
  });

  it('closes on Escape key press or close button click', () => {
    const handleClose = vi.fn();

    render(
      <WardrobePreviewModal
        isOpen={true}
        onClose={handleClose}
        items={mockItems}
        initialItemId="wd_01"
      />
    );

    const closeBtn = screen.getByRole('button', { name: /Close modal/i });
    fireEvent.click(closeBtn);
    expect(handleClose).toHaveBeenCalledTimes(1);

    fireEvent.keyDown(window, { key: 'Escape' });
    expect(handleClose).toHaveBeenCalledTimes(2);
  });

  it('returns null when isOpen is false', () => {
    const { container } = render(
      <WardrobePreviewModal
        isOpen={false}
        onClose={vi.fn()}
        items={mockItems}
      />
    );

    expect(container.firstChild).toBeNull();
  });
});
