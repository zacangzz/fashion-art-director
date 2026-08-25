import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import ComparisonModal from './ComparisonModal';

describe('ComparisonModal', () => {
  const versionA = {
    id: 'gen_1',
    seed: 111,
    is_baseline: true,
    master_image_url: '/api/images/gen_1.png',
    schema_json: { lighting: { color_temperature_k: 5500 } },
  };

  const versionB = {
    id: 'gen_2',
    seed: 111,
    is_baseline: false,
    master_image_url: '/api/images/gen_2.png',
    schema_json: { lighting: { color_temperature_k: 3200 } },
  };

  it('renders split slider diff modal with versions and diff table', () => {
    render(
      <ComparisonModal
        isOpen={true}
        versionA={versionA}
        versionB={versionB}
        onClose={() => {}}
      />
    );

    expect(screen.getByText(/Side-by-Side Split-Slider Diff/i)).toBeInTheDocument();
    expect(screen.getByText(/Version A: #111/i)).toBeInTheDocument();
    expect(screen.getByText(/Version B: #111/i)).toBeInTheDocument();
    expect(screen.getByText(/lighting/i)).toBeInTheDocument();
  });

  it('updates slider range input position', () => {
    render(
      <ComparisonModal
        isOpen={true}
        versionA={versionA}
        versionB={versionB}
        onClose={() => {}}
      />
    );

    const slider = screen.getByRole('slider');
    expect(slider).toBeInTheDocument();
    fireEvent.change(slider, { target: { value: 75 } });
    expect(slider.value).toBe('75');
  });

  it('renders Version A and Version B prompt boxes and supports copying', async () => {
    const mockWriteText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, {
      clipboard: { writeText: mockWriteText },
    });

    const vA = {
      ...versionA,
      compiled_prompt: 'Full prompt for version A',
    };
    const vB = {
      ...versionB,
      compiled_prompt: 'Full prompt for version B',
    };

    render(
      <ComparisonModal
        isOpen={true}
        versionA={vA}
        versionB={vB}
        onClose={() => {}}
      />
    );

    expect(screen.getByText('Full prompt for version A')).toBeInTheDocument();
    expect(screen.getByText('Full prompt for version B')).toBeInTheDocument();

    const copyBtns = screen.getAllByRole('button', { name: /Copy/i });
    await act(async () => {
      fireEvent.click(copyBtns[0]);
    });
    expect(mockWriteText).toHaveBeenCalledWith('Full prompt for version A');
  });
});
