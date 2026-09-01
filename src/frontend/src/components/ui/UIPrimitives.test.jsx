import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { Button, Modal, Badge, Card, Select, Input, Slider } from './index';

describe('UI Primitives Unit Tests', () => {
  describe('Button Primitive', () => {
    it('renders with label and handles click', () => {
      const handleClick = vi.fn();
      render(<Button onClick={handleClick}>Click Me</Button>);
      const btn = screen.getByRole('button', { name: /Click Me/i });
      expect(btn).toBeInTheDocument();
      fireEvent.click(btn);
      expect(handleClick).toHaveBeenCalledTimes(1);
    });

    it('disables button when loading or disabled prop is true', () => {
      const { rerender } = render(<Button disabled>Disabled</Button>);
      expect(screen.getByRole('button')).toBeDisabled();

      rerender(<Button loading>Loading</Button>);
      expect(screen.getByRole('button')).toBeDisabled();
    });
  });

  describe('Modal Primitive', () => {
    it('renders modal dialog when isOpen is true', () => {
      const handleClose = vi.fn();
      render(
        <Modal isOpen={true} onClose={handleClose} title="Test Modal">
          <p>Modal content</p>
        </Modal>
      );
      expect(screen.getByText('Test Modal')).toBeInTheDocument();
      expect(screen.getByText('Modal content')).toBeInTheDocument();
    });

    it('does not render when isOpen is false', () => {
      render(
        <Modal isOpen={false} onClose={vi.fn()} title="Test Modal">
          <p>Modal content</p>
        </Modal>
      );
      expect(screen.queryByText('Test Modal')).not.toBeInTheDocument();
    });

    it('calls onClose when close button or Esc key is pressed', () => {
      const handleClose = vi.fn();
      render(
        <Modal isOpen={true} onClose={handleClose} title="Test Modal">
          <p>Modal content</p>
        </Modal>
      );
      const closeBtn = screen.getByRole('button', { name: /Close dialog/i });
      fireEvent.click(closeBtn);
      expect(handleClose).toHaveBeenCalledTimes(1);

      fireEvent.keyDown(window, { key: 'Escape' });
      expect(handleClose).toHaveBeenCalledTimes(2);
    });
  });

  describe('Badge Primitive', () => {
    it('renders text and handles dismiss', () => {
      const handleDismiss = vi.fn();
      render(
        <Badge variant="success" onDismiss={handleDismiss}>
          Approved
        </Badge>
      );
      expect(screen.getByText('Approved')).toBeInTheDocument();
      const dismissBtn = screen.getByRole('button', { name: /Remove badge/i });
      fireEvent.click(dismissBtn);
      expect(handleDismiss).toHaveBeenCalledTimes(1);
    });
  });

  describe('Card Primitive', () => {
    it('renders title, body and footer', () => {
      render(
        <Card title="Card Title" subtitle="Card Subtitle" footer={<span>Card Footer</span>}>
          <div>Card Body</div>
        </Card>
      );
      expect(screen.getByText('Card Title')).toBeInTheDocument();
      expect(screen.getByText('Card Subtitle')).toBeInTheDocument();
      expect(screen.getByText('Card Body')).toBeInTheDocument();
      expect(screen.getByText('Card Footer')).toBeInTheDocument();
    });
  });

  describe('Select Primitive', () => {
    it('renders options and responds to change', () => {
      const handleChange = vi.fn();
      const options = [
        { value: 'opt1', label: 'Option 1' },
        { value: 'opt2', label: 'Option 2' },
      ];
      render(<Select label="My Select" options={options} onChange={handleChange} />);
      expect(screen.getByLabelText('My Select')).toBeInTheDocument();
      fireEvent.change(screen.getByLabelText('My Select'), { target: { value: 'opt2' } });
      expect(handleChange).toHaveBeenCalled();
    });
  });

  describe('Input Primitive', () => {
    it('renders input and responds to typing', () => {
      const handleChange = vi.fn();
      render(<Input label="Username" onChange={handleChange} />);
      const input = screen.getByLabelText('Username');
      fireEvent.change(input, { target: { value: 'john_doe' } });
      expect(handleChange).toHaveBeenCalled();
    });

    it('renders textarea when multiline is true', () => {
      render(<Input label="Bio" multiline rows={4} />);
      const textarea = screen.getByLabelText('Bio');
      expect(textarea.tagName).toBe('TEXTAREA');
    });
  });

  describe('Slider Primitive', () => {
    it('renders label and handles value change', () => {
      const handleChange = vi.fn();
      render(<Slider label="Temperature" value={0.7} min={0} max={2} step={0.1} onChange={handleChange} />);
      expect(screen.getByText('Temperature')).toBeInTheDocument();
      const slider = screen.getByRole('slider');
      fireEvent.change(slider, { target: { value: '1.2' } });
      expect(handleChange).toHaveBeenCalledWith(1.2);
    });
  });
});
