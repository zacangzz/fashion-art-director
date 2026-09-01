import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import PromptInspector from './PromptInspector';

describe('PromptInspector Component', () => {
  const mockRun = {
    request_id: 'run_123',
    prompt: 'A pristine architectural fashion editorial in Paris with soft daylight.',
    system_instruction: 'You are a world-class fashion director.',
    negative_prompt: 'blurry, distorted, oversaturated',
    narrative: 'High-end Paris street fashion scene with structured tailoring.',
  };

  it('renders primary prompt, system instruction, and negative prompt', () => {
    render(<PromptInspector run={mockRun} />);

    expect(screen.getByText(/Prompt Formulation & System Instructions/i)).toBeInTheDocument();
    expect(screen.getByText(/A pristine architectural fashion editorial in Paris/i)).toBeInTheDocument();
    expect(screen.getByText(/You are a world-class fashion director/i)).toBeInTheDocument();
    expect(screen.getByText(/blurry, distorted, oversaturated/i)).toBeInTheDocument();
    expect(screen.getByText(/High-end Paris street fashion scene/i)).toBeInTheDocument();
  });

  it('supports activeStep inspection and displays step badge', () => {
    const mockStep = {
      label: 'Vision Analysis Pass',
      event: {
        prompts: { prompt: 'Extracted moodboard aesthetic direction' },
        instruction: 'Multimodal vision extraction directive',
      },
    };
    const onReset = vi.fn();

    render(<PromptInspector run={mockRun} activeStep={mockStep} onResetStep={onReset} />);

    expect(screen.getByText(/Inspecting: Vision Analysis Pass/i)).toBeInTheDocument();
    expect(screen.getByText(/Extracted moodboard aesthetic direction/i)).toBeInTheDocument();
    expect(screen.getByText(/Multimodal vision extraction directive/i)).toBeInTheDocument();

    const resetBtn = screen.getByRole('button', { name: /Reset to Full Run/i });
    fireEvent.click(resetBtn);
    expect(onReset).toHaveBeenCalled();
  });
});
