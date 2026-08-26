import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import ExportStudio, { RATIO_PRESETS } from './ExportStudio';

describe('ExportStudio Component', () => {
  const mockGenResult = {
    generation_id: 'gen_export_123',
    master_image_url: 'https://example.com/master.png',
    seed: 9876543,
    compiled_prompt: 'Editorial portrait of a model in haute couture suit',
  };

  it('renders all production and 4K aspect ratio preview cards', () => {
    render(<ExportStudio generationResult={mockGenResult} />);

    expect(screen.getByText('Export & Multi-Ratio Production Studio')).toBeInTheDocument();
    expect(screen.getByText('Aspect Ratio Crops Live Preview')).toBeInTheDocument();

    // Verify all ratio presets are present
    RATIO_PRESETS.forEach((preset) => {
      expect(screen.getAllByText(preset.id).length).toBeGreaterThan(0);
      expect(screen.getAllByText(preset.label).length).toBeGreaterThan(0);
    });
  });

  it('allows selecting different ratio cards to update enlarged inspector', () => {
    render(<ExportStudio generationResult={mockGenResult} />);

    // Initially 1:1 is selected
    expect(screen.getByText(/Inspector: 1:1 Square/i)).toBeInTheDocument();

    // Click on 9:16 Story card
    const storyTab = screen.getByRole('tab', { name: /9:16 Story \/ Reels/i });
    fireEvent.click(storyTab);

    expect(screen.getByText(/Inspector: 9:16 Story \/ Reels/i)).toBeInTheDocument();
  });

  it('triggers onExportBundle when 1-click bundle button is clicked', () => {
    const handleExport = vi.fn();
    render(
      <ExportStudio
        generationResult={mockGenResult}
        onExportBundle={handleExport}
      />
    );

    const bundleBtn = screen.getByRole('button', { name: /Download Production & 4K Bundle/i });
    fireEvent.click(bundleBtn);

    expect(handleExport).toHaveBeenCalledWith('gen_export_123');
  });


  it('allows toggling between PNG and JPEG format and adjusting quality', () => {
    render(<ExportStudio generationResult={mockGenResult} />);

    const jpegBtn = screen.getByRole('button', { name: /JPEG \(Compressed\)/i });
    fireEvent.click(jpegBtn);

    expect(screen.getByText('JPEG Quality:')).toBeInTheDocument();
    expect(screen.getByText('95%')).toBeInTheDocument();

    const slider = screen.getByLabelText(/JPEG Compression Quality/i);
    fireEvent.change(slider, { target: { value: '80' } });
    expect(screen.getByText('80%')).toBeInTheDocument();
  });
});
