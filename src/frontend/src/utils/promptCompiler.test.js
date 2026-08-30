import { describe, it, expect } from 'vitest';
import {
  extractCategoryLabels,
  getModifiedCategories,
  compileModularPrompt,
  compileDeltaPrompt,
} from './promptCompiler';

describe('promptCompiler', () => {
  const baseCategories = {
    subject_details: [{ id: '1', label: 'chic model', weight: 1.0, enabled: true }],
    wardrobe_hair: [{ id: '2', label: 'black leather jacket', weight: 1.0, enabled: true }],
    environment: [{ id: '3', label: 'brutalist concrete alley', weight: 1.0, enabled: true }],
    lighting: [{ id: '4', label: 'golden hour rim light', weight: 1.5, enabled: true }],
  };

  describe('extractCategoryLabels', () => {
    it('extracts active category labels cleanly', () => {
      const labels = extractCategoryLabels(baseCategories, 'lighting');
      expect(labels).toEqual(['golden hour rim light']);
    });

    it('ignores disabled chips', () => {
      const cats = {
        lighting: [{ id: '4', label: 'neon blue', weight: 1.0, enabled: false }],
      };
      const labels = extractCategoryLabels(cats, 'lighting');
      expect(labels).toEqual([]);
    });
  });

  describe('getModifiedCategories', () => {
    it('detects modified category when tag labels change', () => {
      const currentCategories = {
        ...baseCategories,
        wardrobe_hair: [{ id: '2', label: 'crimson silk trench coat', weight: 1.0, enabled: true }],
      };

      const diff = getModifiedCategories(
        currentCategories,
        baseCategories,
        'Base scene',
        'Base scene'
      );

      expect(diff.hasChanges).toBe(true);
      expect(diff.categories.wardrobe_hair).toBe(true);
      expect(diff.categories.environment).toBeUndefined();
      expect(diff.narrative).toBe(false);
    });

    it('detects narrative change', () => {
      const diff = getModifiedCategories(
        baseCategories,
        baseCategories,
        'Updated narrative direction',
        'Initial narrative'
      );

      expect(diff.hasChanges).toBe(true);
      expect(diff.narrative).toBe(true);
    });
  });

  describe('compileModularPrompt', () => {
    it('compiles directly from 9-category visual levers without narrative', () => {
      const compiled = compileModularPrompt(baseCategories);
      expect(compiled).toContain('Subject: chic model, wearing black leather jacket.');
      expect(compiled).toContain('Environment: set in brutalist concrete alley.');
      expect(compiled).toContain('Lighting & Color: illuminated with golden hour rim light.');
    });

    it('compiles full 9-category structured prompt with legacy narrative if provided', () => {
      const compiled = compileModularPrompt('A dramatic editorial portrait.', baseCategories);
      expect(compiled).toContain('A dramatic editorial portrait.');
      expect(compiled).toContain('Subject: chic model, wearing black leather jacket.');
      expect(compiled).toContain('Environment: set in brutalist concrete alley.');
      expect(compiled).toContain('Lighting & Color: illuminated with golden hour rim light.');
    });

    it('honors prompt override', () => {
      const compiled = compileModularPrompt(baseCategories, [], 'Custom forced prompt');
      expect(compiled).toBe('Custom forced prompt');
    });
  });

  describe('compileDeltaPrompt', () => {
    it('falls back to modular prompt when no baseline is provided', () => {
      const prompt = compileDeltaPrompt({
        narrative: 'Scene narrative',
        categories: baseCategories,
        baselineCategories: null,
      });
      expect(prompt).toContain('Subject: chic model, wearing black leather jacket.');
    });

    it('generates structured preservation and delta adjustments when tags are modified', () => {
      const updatedCategories = {
        ...baseCategories,
        wardrobe_hair: [{ id: '2', label: 'red oversized bomber jacket', weight: 1.0, enabled: true }],
      };

      const prompt = compileDeltaPrompt({
        narrative: 'A dramatic editorial portrait.',
        categories: updatedCategories,
        baselineNarrative: 'A dramatic editorial portrait.',
        baselineCategories: baseCategories,
        lockedCategories: ['subject_details', 'environment'],
      });

      expect(prompt).toContain('Visual Reference Foundation: Use the reference image as the structural');
      expect(prompt).toContain('Requested Modifications: Wardrobe & Hairstyle: wearing red oversized bomber jacket.');
      expect(prompt).toContain('Consistent Anchors:');
      expect(prompt).toContain('Subject & Character Details');
      expect(prompt).toContain('Environment & Setting');
      expect(prompt).not.toContain('Color Profile & Palette');
      expect(prompt).not.toContain('Mood, Vibe & Era');

      const unlockedPrompt = compileDeltaPrompt({
        narrative: 'A dramatic editorial portrait.',
        categories: updatedCategories,
        baselineNarrative: 'A dramatic editorial portrait.',
        baselineCategories: baseCategories,
        lockedCategories: [],
      });
      expect(unlockedPrompt).not.toContain('Consistent Anchors:');
    });

    it('returns consistency directive when no modifications exist', () => {
      const prompt = compileDeltaPrompt({
        narrative: 'Same narrative',
        categories: baseCategories,
        baselineNarrative: 'Same narrative',
        baselineCategories: baseCategories,
      });

      expect(prompt).toContain('Visual Continuity: Faithfully preserve the character identity');
    });
  });
});
