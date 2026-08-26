import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import ExportStudio from './ExportStudio';
import * as apiClient from '../services/apiClient';

describe('ExportStudio Component', () => {
  const mockGenResult = {
    generation_id: 'gen_export_123',
    master_image_url: 'https://example.com/master.png',
    seed: 9876543,
    aspect_ratio: '2:3',
    compiled_prompt: 'Editorial portrait of a model in haute couture suit',
  };

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders original preview thumbnail, metadata, and Prepare for Export button', () => {
    render(<ExportStudio generationResult={mockGenResult} />);

    expect(screen.getByText('Master Export & AI Restoration Studio')).toBeInTheDocument();
    expect(screen.getAllByText(/Format: 2:3/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/Original Preview/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Prepare for Export/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Download Original Master/i })).toBeInTheDocument();
  });

  it('handles Prepare for Export API call and displays AI Enhanced Master', async () => {
    const mockPreparedResult = {
      generation_id: 'gen_export_master_456',
      parent_id: 'gen_export_123',
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
      expect(prepareSpy).toHaveBeenCalledWith('gen_export_123');
      expect(screen.getByText(/AI Enhanced Master Ready/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Download High Quality Master \(\.png\)/i })).toBeInTheDocument();
      expect(onMasterPrepared).toHaveBeenCalledWith(mockPreparedResult);
    });
  });

  it('allows toggling between Split, Enhanced, and Original compare modes once prepared', async () => {
    const mockPreparedResult = {
      generation_id: 'gen_export_master_456',
      parent_id: 'gen_export_123',
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

    const originalModeBtn = screen.getByRole('button', { name: /Original/i });
    fireEvent.click(originalModeBtn);
    expect(originalModeBtn).toHaveClass('active');
  });
});

