import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  analyzeAndGenerateBaselines,
  analyzeMoodboard,
  fineTuneGeneration,
  fetchHistory,
  fetchGeneration,
  fetchLineage,
  restoreGeneration,
  exportBundle,
  prepareExport,
  generateImage,
  resyncPromptFromLevers,
  resyncLeversFromPrompt,
} from './apiClient';

describe('apiClient', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  it('analyzeAndGenerateBaselines posts FormData to /api/moodboard/analyze-and-baselines', async () => {
    const mockResponse = {
      moodboard_id: 'mb_123',
      schema: { intent: {} },
      baselines: [{ id: 'gen_1', seed: 111, image_url: '/api/images/gen_1.png' }],
    };
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    const file = new File(['dummy'], 'test.png', { type: 'image/png' });
    const result = await analyzeAndGenerateBaselines([file]);

    expect(fetch).toHaveBeenCalledWith('/api/moodboard/analyze-and-baselines', expect.objectContaining({
      method: 'POST',
      body: expect.any(FormData),
    }));
    expect(result).toEqual(mockResponse);
  });

  it('analyzeAndGenerateBaselines includes prompt in FormData when provided', async () => {
    const mockResponse = {
      moodboard_id: 'mb_123',
      schema: { intent: { primary_goal: 'Editorial villa' } },
      baselines: [],
    };
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    const file = new File(['dummy'], 'test.png', { type: 'image/png' });
    const result = await analyzeAndGenerateBaselines([file], 'Editorial villa at sunset');

    expect(fetch).toHaveBeenCalledWith('/api/moodboard/analyze-and-baselines', expect.objectContaining({
      method: 'POST',
      body: expect.any(FormData),
    }));
    expect(result).toEqual(mockResponse);
  });

  it('fineTuneGeneration posts JSON to /api/generate/fine-tune', async () => {
    const mockResult = {
      generation_id: 'gen_child_1',
      parent_id: 'gen_base_1',
      seed: 918231,
      compiled_prompt: 'prompt',
      negative_prompt: 'neg',
      image_url: '/api/images/gen_child_1.png',
    };
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockResult,
    });

    const payload = {
      parent_id: 'gen_base_1',
      schema: { intent: {} },
      seed_mode: 'locked',
      seed: 918231,
    };

    const res = await fineTuneGeneration(payload);
    expect(fetch).toHaveBeenCalledWith('/api/generate/fine-tune', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify(payload),
    }));
    expect(res).toEqual(mockResult);
  });

  it('handles 404 Not Found error with clear descriptive message', async () => {
    fetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
      json: async () => ({ detail: 'Google AI Model Not Found (404): gemini-3.1-flash-lite-image not available' }),
    });

    await expect(fineTuneGeneration({ parent_id: 'gen_1' })).rejects.toThrow(
      /Google AI Model Not Found/i
    );
  });

  it('fetchHistory gets /api/history', async () => {
    const mockResult = { generations: [{ id: 'gen_1' }] };
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockResult,
    });

    const res = await fetchHistory();
    expect(fetch).toHaveBeenCalledWith('/api/history', expect.anything());
    expect(res).toEqual(mockResult);
  });

  it('restoreGeneration posts to /api/generations/:id/restore', async () => {
    const mockResult = { id: 'gen_1', seed: 123 };
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockResult,
    });

    const res = await restoreGeneration('gen_1');
    expect(fetch).toHaveBeenCalledWith('/api/generations/gen_1/restore', expect.objectContaining({
      method: 'POST',
    }));
    expect(res).toEqual(mockResult);
  });

  it('exportBundle posts to /api/export/bundle and returns blob', async () => {
    const mockBlob = new Blob(['zip bytes'], { type: 'application/zip' });
    fetch.mockResolvedValueOnce({
      ok: true,
      blob: async () => mockBlob,
    });

    const res = await exportBundle('gen_456');
    expect(fetch).toHaveBeenCalledWith('/api/export/bundle', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ generation_id: 'gen_456' }),
    }));
    expect(res).toEqual(mockBlob);
  });

  it('prepareExport posts to /api/export/prepare and returns enhanced master data', async () => {
    const mockResult = {
      generation_id: 'gen_export_789',
      parent_id: 'gen_456',
      master_image_url: '/api/images/gen_export_789_master.png',
      aspect_ratio: '2:3',
      resolution: { width: 1080, height: 1620 },
      created_at: '2026-08-26T00:00:00Z',
    };
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockResult,
    });

    const res = await prepareExport('gen_456');
    expect(fetch).toHaveBeenCalledWith('/api/export/prepare', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ generation_id: 'gen_456' }),
    }));
    expect(res).toEqual(mockResult);
  });

  it('resyncPromptFromLevers posts to /api/moodboard/resync-prompt', async () => {
    const mockResult = {
      master_prompt: 'Synthesized high fashion prompt',
      narrative: 'Updated narrative',
      conflicts: [],
    };
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockResult,
    });

    const payload = {
      narrative: 'Scene narrative',
      categories: { lighting: [{ label: 'soft golden light' }] },
    };
    const res = await resyncPromptFromLevers(payload);
    expect(fetch).toHaveBeenCalledWith('/api/moodboard/resync-prompt', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify(payload),
    }));
    expect(res).toEqual(mockResult);
  });

  it('resyncLeversFromPrompt posts to /api/moodboard/resync-levers', async () => {
    const mockResult = {
      categories: { subject_details: [{ label: 'striking model' }] },
      narrative: 'Extracted narrative',
      conflicts: [],
    };
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockResult,
    });

    const payload = {
      master_prompt: 'High fashion editorial photo with striking model.',
      narrative: 'Editorial scene',
    };
    const res = await resyncLeversFromPrompt(payload);
    expect(fetch).toHaveBeenCalledWith('/api/moodboard/resync-levers', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify(payload),
    }));
    expect(res).toEqual(mockResult);
  });
});
