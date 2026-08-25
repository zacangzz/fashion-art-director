import '@testing-library/jest-dom';
import { vi } from 'vitest';

if (typeof window !== 'undefined' && !window.URL.createObjectURL) {
  window.URL.createObjectURL = vi.fn(() => 'blob:mock-url');
}
