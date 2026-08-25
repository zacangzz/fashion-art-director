import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import App from './App';

describe('App Component Workflow', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ generations: [] }),
    }));
  });

  it('renders Step 1 Moodboard Ingestion layout on initial load', () => {
    render(<App />);
    expect(screen.getByText('Image Gen Pipeline Studio')).toBeInTheDocument();
    expect(screen.getByText(/1. Moodboard & Baselines/i)).toBeInTheDocument();
    expect(screen.getByText(/Moodboard Ingestion/i)).toBeInTheDocument();
  });

  it('switches between Step 1 and Step 2 and toggles between Tag Studio and Canvas Studio', () => {
    render(<App />);

    const step2Btn = screen.getByRole('button', { name: /2\. Studio Workspace/i });
    fireEvent.click(step2Btn);

    // Should show Macro Studio by default
    expect(screen.getByText(/Macro Studio \(Visual Levers & Prompt Compiler\)/i)).toBeInTheDocument();
    expect(screen.getByText(/4K Master Canvas Viewport/i)).toBeInTheDocument();

    // Switch to Canvas Studio tab
    const canvasTabBtn = screen.getByRole('button', { name: /Micro Studio \(Canvas\)/i });
    fireEvent.click(canvasTabBtn);

    expect(screen.getByText(/Spatial Precision/i)).toBeInTheDocument();
    expect(screen.getByText(/Targeted Edit Instruction/i)).toBeInTheDocument();

    // Switch back to Tag Studio tab
    const tagTabBtn = screen.getByRole('button', { name: /Macro Studio \(Tags\)/i });
    fireEvent.click(tagTabBtn);

    expect(screen.getByText(/Macro Studio \(Visual Levers & Prompt Compiler\)/i)).toBeInTheDocument();
  });

  it('opens History Drawer when history button is clicked', async () => {
    render(<App />);

    const historyBtn = screen.getByRole('button', { name: /Lineage History/i });
    fireEvent.click(historyBtn);

    expect(screen.getByText(/Generation Lineage & History/i)).toBeInTheDocument();
  });
});
