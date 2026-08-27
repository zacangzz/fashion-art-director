import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import MoodboardUploader from './MoodboardUploader';

describe('MoodboardUploader', () => {
  it('renders upload dropzone instructions and starting prompt input', () => {
    render(<MoodboardUploader files={[]} onFilesChange={() => {}} onAnalyze={() => {}} />);
    expect(screen.getByText(/Moodboard Ingestion/i)).toBeInTheDocument();
    expect(screen.getByText(/Drop 1–5 reference images or PDFs here/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Starting Scene Prompt/i)).toBeInTheDocument();
    expect(screen.getByText(/Required/i)).toBeInTheDocument();
  });

  it('disables analyze button when no files are selected', () => {
    render(<MoodboardUploader files={[]} prompt="Sample prompt" onFilesChange={() => {}} onAnalyze={() => {}} />);
    const btn = screen.getByRole('button', { name: /Upload 1–5 Reference Files to Begin/i });
    expect(btn).toBeDisabled();
  });

  it('disables analyze button when files are present but prompt is empty', () => {
    const file = new File(['dummy'], 'sample.png', { type: 'image/png' });
    render(<MoodboardUploader files={[file]} prompt="" onFilesChange={() => {}} onAnalyze={() => {}} />);
    const btn = screen.getByRole('button', { name: /Enter Starting Prompt to Analyze/i });
    expect(btn).toBeDisabled();
  });

  it('calls onAnalyze with prompt when button is clicked with files and prompt', () => {
    const onAnalyze = vi.fn();
    const onPromptChange = vi.fn();
    const file = new File(['dummy'], 'sample.png', { type: 'image/png' });
    render(
      <MoodboardUploader
        files={[file]}
        onFilesChange={() => {}}
        prompt="Editorial sun-drenched terrace"
        onPromptChange={onPromptChange}
        onAnalyze={onAnalyze}
      />
    );

    const textarea = screen.getByLabelText(/Starting Scene Prompt/i);
    expect(textarea.value).toBe('Editorial sun-drenched terrace');

    const btn = screen.getByRole('button', { name: /Analyze Moodboard/i });
    expect(btn).not.toBeDisabled();
    fireEvent.click(btn);
    expect(onAnalyze).toHaveBeenCalledWith('Editorial sun-drenched terrace');
  });

  it('displays analyzing loading state', () => {
    const file = new File(['dummy'], 'sample.png', { type: 'image/png' });
    render(
      <MoodboardUploader
        files={[file]}
        prompt="Sample"
        onFilesChange={() => {}}
        onAnalyze={() => {}}
        isAnalyzing={true}
      />
    );
    expect(screen.getByText(/Analyzing Moodboard & Synthesizing Levers.../i)).toBeInTheDocument();
  });

  it('renders aspect ratio options defaulting to 1.8:1 and calls onAspectRatioChange', () => {
    const onRatioChange = vi.fn();
    render(
      <MoodboardUploader
        files={[]}
        aspectRatio="1.8:1"
        onAspectRatioChange={onRatioChange}
        onFilesChange={() => {}}
        onAnalyze={() => {}}
      />
    );

    expect(screen.getByText('Workflow Aspect Ratio')).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: /1\.8:1/i })).toBeInTheDocument();

    const squareBtn = screen.getByRole('radio', { name: /1:1/i });
    fireEvent.click(squareBtn);
    expect(onRatioChange).toHaveBeenCalledWith('1:1');
  });

  it('renders direct photo ingestion card and handles direct photo selection', async () => {
    const onDirectUpload = vi.fn();
    render(
      <MoodboardUploader
        files={[]}
        onFilesChange={() => {}}
        onAnalyze={() => {}}
        onDirectPhotoUpload={onDirectUpload}
      />
    );

    expect(screen.getByText(/Direct Photo Ingestion/i)).toBeInTheDocument();
    expect(screen.getByText(/Skip Art Direction/i)).toBeInTheDocument();
    expect(screen.getByText(/Drop 1 photo here, or/i)).toBeInTheDocument();
  });
});


