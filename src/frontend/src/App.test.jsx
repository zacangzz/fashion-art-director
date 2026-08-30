import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import App from './App';

describe('App Component Workflow', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ generations: [] }),
    }));
  });

  it('renders Step 1 Art Direction layout on initial load', () => {
    render(<App />);
    expect(screen.getByText('Fashion AI')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /1 Art Direction/i })).toBeInTheDocument();
    expect(screen.getByText(/Moodboard Ingestion/i)).toBeInTheDocument();
    expect(screen.getByText(/Direct Photo Ingestion/i)).toBeInTheDocument();
  });

  it('renders workflow step navigation items', () => {
    render(<App />);

    expect(screen.getByRole('button', { name: /1 Art Direction/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /2 Refinement/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /3 Canvas/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /4 Wardrobe/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /5 Export/i })).toBeInTheDocument();
  });

  it('opens History Drawer when history button is clicked', async () => {
    render(<App />);

    const historyBtn = screen.getByRole('button', { name: /Lineage History/i });
    fireEvent.click(historyBtn);

    expect(screen.getByText(/Generation Lineage & History/i)).toBeInTheDocument();
  });
});

