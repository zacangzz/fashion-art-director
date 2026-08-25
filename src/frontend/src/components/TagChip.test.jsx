import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import React from 'react';
import TagChip from './TagChip';

describe('TagChip component', () => {
  const sampleChip = {
    id: 'chip-1',
    category: 'subject_details',
    label: 'Cyberpunk Warrior',
    enabled: true,
    locked: false,
    weight: 1.0,
    isCustom: false,
  };

  it('renders chip label and weight badge', () => {
    render(<TagChip chip={sampleChip} onUpdate={vi.fn()} onDelete={vi.fn()} />);
    expect(screen.getByText('Cyberpunk Warrior')).toBeInTheDocument();
    expect(screen.getByText('1.0x')).toBeInTheDocument();
  });

  it('toggles lock state when lock icon is clicked', () => {
    const handleUpdate = vi.fn();
    render(<TagChip chip={sampleChip} onUpdate={handleUpdate} onDelete={vi.fn()} />);

    const lockBtn = screen.getByRole('button', { name: /lock/i });
    fireEvent.click(lockBtn);

    expect(handleUpdate).toHaveBeenCalledWith('chip-1', expect.objectContaining({
      locked: true,
    }));
  });

  it('enters inline edit mode on label click and submits new label on enter', () => {
    const handleUpdate = vi.fn();
    render(<TagChip chip={sampleChip} onUpdate={handleUpdate} onDelete={vi.fn()} />);

    const labelSpan = screen.getByText('Cyberpunk Warrior');
    fireEvent.click(labelSpan);

    const input = screen.getByDisplayValue('Cyberpunk Warrior');
    fireEvent.change(input, { target: { value: 'Neon Mech Warrior' } });
    fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' });

    expect(handleUpdate).toHaveBeenCalledWith('chip-1', expect.objectContaining({
      label: 'Neon Mech Warrior',
      enabled: true,
    }));
  });

  it('updates weight when weight stepper is clicked', () => {
    const handleUpdate = vi.fn();
    render(<TagChip chip={sampleChip} onUpdate={handleUpdate} onDelete={vi.fn()} />);

    const weightBadge = screen.getByText('1.0x');
    fireEvent.click(weightBadge);

    expect(handleUpdate).toHaveBeenCalledWith('chip-1', expect.objectContaining({
      weight: 1.1,
      enabled: true,
    }));
  });

  it('calls onDelete when delete button is clicked', () => {
    const handleDelete = vi.fn();
    render(<TagChip chip={{ ...sampleChip, isCustom: true }} onUpdate={vi.fn()} onDelete={handleDelete} />);

    const deleteBtn = screen.getByRole('button', { name: /delete/i });
    fireEvent.click(deleteBtn);

    expect(handleDelete).toHaveBeenCalledWith('chip-1');
  });
});
