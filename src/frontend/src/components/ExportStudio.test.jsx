import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import ExportStudio from './ExportStudio';
import * as apiClient from '../services/apiClient';

describe('ExportStudio Component', () => {
  const mockGenResult = {
    generation_id: 'gen_123',
    master_image_url: 'https://example.com/master_original.png',
    seed: 9876543,
    aspect_ratio: '2:3',
    compiled_prompt: 'Editorial portrait of a model in haute couture suit',
    resolution_width: 1080,
    resolution_height: 1620,
  };

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders preview thumbnail, metadata, and download options for original and upscaled images', () => {
    render(<ExportStudio generationResult={mockGenResult} />);

    expect(screen.getByText('Master Export & AI Restoration Studio')).toBeInTheDocument();
    expect(screen.getAllByText(/Format: 2:3/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/Original Preview/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Prepare for Export/i })).toBeInTheDocument();

    // Original Image download option
    expect(screen.getByText('Original Generated Image')).toBeInTheDocument();
    const downloadOriginalBtn = screen.getByRole('button', { name: /Download Original Image \(\.png\)/i });
    expect(downloadOriginalBtn).toBeInTheDocument();
    expect(downloadOriginalBtn).toBeEnabled();

    // AI-Upscaled Master download option
    expect(screen.getByText('AI-Upscaled Master')).toBeInTheDocument();
    const downloadUpscaledBtn = screen.getByRole('button', { name: /Prepare in Step 1 to Download/i });
    expect(downloadUpscaledBtn).toBeInTheDocument();
    expect(downloadUpscaledBtn).toBeDisabled();
  });

  it('handles Prepare for Export API call and enables AI-Upscaled Master download option', async () => {
    const mockPreparedResult = {
      generation_id: 'gen_export_master_456',
      parent_id: 'gen_123',
      master_image_url: 'https://example.com/master_enhanced.png',
      aspect_ratio: '2:3',
      resolution: { width: 2160, height: 3240 },
      seed: 9876543,
      compiled_prompt: 'Editorial portrait of a model in haute couture suit',
      created_at: '2026-08-26T00:00:00Z',
    };

    const prepareSpy = vi.spyOn(apiClient, 'prepareExport').mockResolvedValueOnce(mockPreparedResult);
    const onMasterPrepared = vi.fn();

    render(
      <ExportStudio
        generationResult={mockGenResult}
        onExportMasterPrepared={onMasterPrepared}
      />
    );

    const prepareBtn = screen.getByRole('button', { name: /Prepare for Export/i });
    fireEvent.click(prepareBtn);

    await waitFor(() => {
      expect(prepareSpy).toHaveBeenCalledWith('gen_123');
      expect(screen.getByText(/AI Enhanced Master Ready/i)).toBeInTheDocument();
      expect(onMasterPrepared).toHaveBeenCalledWith(mockPreparedResult);
    });

    // Both download buttons should be available and active
    expect(screen.getByRole('button', { name: /Download Original Image \(\.png\)/i })).toBeEnabled();
    const upscaledBtn = screen.getByRole('button', { name: /Download Upscaled Master \(\.png\)/i });
    expect(upscaledBtn).toBeInTheDocument();
    expect(upscaledBtn).toBeEnabled();
  });

  it('downloads original image when Download Original Image is clicked', async () => {
    const fetchSpy = vi.fn().mockResolvedValue({
      blob: async () => new Blob(['mock-image-data'], { type: 'image/png' }),
    });
    vi.stubGlobal('fetch', fetchSpy);
    vi.stubGlobal('URL', {
      createObjectURL: vi.fn(() => 'blob:mock-url'),
      revokeObjectURL: vi.fn(),
    });

    render(<ExportStudio generationResult={mockGenResult} />);

    const downloadOriginalBtn = screen.getByRole('button', { name: /Download Original Image \(\.png\)/i });
    fireEvent.click(downloadOriginalBtn);

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith('https://example.com/master_original.png');
    });
  });

  it('allows toggling between Split, Enhanced, and Original compare modes once prepared', async () => {
    const mockPreparedResult = {
      generation_id: 'gen_export_master_456',
      parent_id: 'gen_123',
      master_image_url: 'https://example.com/master_enhanced.png',
      aspect_ratio: '2:3',
      resolution: { width: 2160, height: 3240 },
    };

    vi.spyOn(apiClient, 'prepareExport').mockResolvedValueOnce(mockPreparedResult);

    render(<ExportStudio generationResult={mockGenResult} />);

    const prepareBtn = screen.getByRole('button', { name: /Prepare for Export/i });
    fireEvent.click(prepareBtn);

    await waitFor(() => {
      expect(screen.getByText(/AI Enhanced Master Ready/i)).toBeInTheDocument();
    });

    const enhancedModeBtn = screen.getByRole('button', { name: /Enhanced/i });
    fireEvent.click(enhancedModeBtn);
    expect(enhancedModeBtn).toHaveClass('active');

    const originalModeBtn = screen.getByRole('button', { name: /^Original$/i });
    fireEvent.click(originalModeBtn);
    expect(originalModeBtn).toHaveClass('active');
  });

  it('downloads upscaled master image when Download Upscaled Master is clicked', async () => {
    const mockPreparedResult = {
      generation_id: 'gen_export_master_456',
      parent_id: 'gen_123',
      master_image_url: 'https://example.com/master_enhanced.png',
      aspect_ratio: '2:3',
      resolution: { width: 2160, height: 3240 },
    };

    vi.spyOn(apiClient, 'prepareExport').mockResolvedValueOnce(mockPreparedResult);

    const fetchSpy = vi.fn().mockResolvedValue({
      blob: async () => new Blob(['mock-upscaled-data'], { type: 'image/png' }),
    });
    vi.stubGlobal('fetch', fetchSpy);
    vi.stubGlobal('URL', {
      createObjectURL: vi.fn(() => 'blob:mock-upscaled-url'),
      revokeObjectURL: vi.fn(),
    });

    render(<ExportStudio generationResult={mockGenResult} />);

    const prepareBtn = screen.getByRole('button', { name: /Prepare for Export/i });
    fireEvent.click(prepareBtn);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Download Upscaled Master \(\.png\)/i })).toBeEnabled();
    });

    const downloadUpscaledBtn = screen.getByRole('button', { name: /Download Upscaled Master \(\.png\)/i });
    fireEvent.click(downloadUpscaledBtn);

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith('https://example.com/master_enhanced.png');
    });
  });
});



