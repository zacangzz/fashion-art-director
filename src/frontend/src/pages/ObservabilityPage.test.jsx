import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import ObservabilityPage from './ObservabilityPage';
import * as apiClient from '../services/apiClient';

vi.mock('../services/apiClient', () => ({
  fetchTelemetryEvents: vi.fn(),
  fetchRequestTrace: vi.fn(),
  fetchTelemetryStats: vi.fn(),
  fetchSystemLogs: vi.fn(),
  fetchDatabaseSummary: vi.fn(),
  fetchDatabaseTableRecords: vi.fn(),
}));

describe('ObservabilityPage', () => {
  const mockEvents = [
    {
      timestamp: '2026-08-26T10:00:00Z',
      event: 'fine_tune_request',
      event_type: 'fine_tune_request',
      request_id: 'req_test_123',
      component: 'generation',
      status: 'success',
      model: 'gemini-3.1-flash-lite-image',
      duration_ms: 850.5,
      final_prompt: 'Cinematic portrait with rim light',
      seed: 4289102,
      aspect_ratio: '2:3',
    },
    {
      timestamp: '2026-08-26T10:01:00Z',
      event: 'vision_error',
      event_type: 'vision_error',
      request_id: 'req_vis_error_1',
      component: 'vision',
      status: 'error',
      error: 'Model timeout after 10000ms',
    },
  ];

  const mockStats = {
    total_events: 2,
    error_count: 1,
    success_rate: 50.0,
    components: { generation: 1, vision: 1 },
    event_types: { fine_tune_request: 1, vision_error: 1 },
    average_latencies_ms: { 'gemini-3.1-flash-lite-image': 850.5 },
  };

  const mockLogs = {
    total_lines: 2,
    logs: [
      '2026-08-26 10:00:00 [INFO] [req:req_test_123] [studio.generation:45] Generation started',
      '2026-08-26 10:01:00 [ERROR] [req:req_vis_error_1] [studio.vision:88] Model timeout',
    ],
  };

  const mockDbSummary = {
    generations: { row_count: 12, columns: [{ name: 'id', type: 'TEXT' }] },
    moodboards: { row_count: 3, columns: [{ name: 'id', type: 'TEXT' }] },
    wardrobe_items: { row_count: 8, columns: [{ name: 'id', type: 'TEXT' }] },
  };

  const mockDbRows = {
    table: 'generations',
    total: 1,
    limit: 25,
    offset: 0,
    rows: [
      {
        id: 'gen_001',
        parent_id: null,
        is_baseline: true,
        seed: 4289102,
        compiled_prompt: 'Cinematic portrait',
        created_at: '2026-08-26T10:00:00Z',
      },
    ],
  };

  beforeEach(() => {
    vi.clearAllMocks();
    apiClient.fetchTelemetryEvents.mockResolvedValue({
      total: 2,
      limit: 50,
      offset: 0,
      events: mockEvents,
    });
    apiClient.fetchTelemetryStats.mockResolvedValue(mockStats);
    apiClient.fetchSystemLogs.mockResolvedValue(mockLogs);
    apiClient.fetchDatabaseSummary.mockResolvedValue(mockDbSummary);
    apiClient.fetchDatabaseTableRecords.mockResolvedValue(mockDbRows);
    apiClient.fetchRequestTrace.mockResolvedValue([mockEvents[0]]);
  });

  it('renders page header, KPI cards, and default telemetry events list', async () => {
    render(<ObservabilityPage />);

    expect(screen.getByText(/Studio Observability & System Intelligence/i)).toBeInTheDocument();
    expect(screen.getByText(/Studio Pipeline/i)).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getAllByText(/fine_tune_request/i).length).toBeGreaterThan(0);
      expect(screen.getAllByText(/vision_error/i).length).toBeGreaterThan(0);
    });

    expect(screen.getByText(/50.0%/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Cinematic portrait with rim light/i).length).toBeGreaterThan(0);
  });

  it('allows switching to Live System Logs tab and viewing rotating logs', async () => {
    render(<ObservabilityPage />);

    const logsTabBtn = screen.getByRole('button', { name: /Live System Logs/i });
    fireEvent.click(logsTabBtn);

    await waitFor(() => {
      expect(screen.getByText(/storage\/logs\/studio.log/i)).toBeInTheDocument();
      expect(screen.getByText(/Generation started/i)).toBeInTheDocument();
      expect(screen.getByText(/Model timeout/i)).toBeInTheDocument();
    });
  });

  it('allows switching to Database Explorer tab and viewing SQLite tables and records', async () => {
    render(<ObservabilityPage />);

    const dbTabBtn = screen.getByRole('button', { name: /Database Explorer/i });
    fireEvent.click(dbTabBtn);

    await waitFor(() => {
      expect(screen.getByText(/Table:/i)).toBeInTheDocument();
      expect(screen.getAllByText(/generations/i).length).toBeGreaterThan(0);
      expect(screen.getByText('gen_001')).toBeInTheDocument();
      expect(screen.getByText(/Cinematic portrait/i)).toBeInTheDocument();
    });
  });

  it('allows switching to Metrics & Distribution tab', async () => {
    render(<ObservabilityPage />);

    const statsTabBtn = screen.getByRole('button', { name: /Metrics & Distribution/i });
    fireEvent.click(statsTabBtn);

    await waitFor(() => {
      expect(screen.getByText(/Component Request Volume/i)).toBeInTheDocument();
      expect(screen.getByText(/Average Model Latency/i)).toBeInTheDocument();
      expect(screen.getByText(/Event Types Breakdown/i)).toBeInTheDocument();
    });
  });
});
