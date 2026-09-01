import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import ObservabilityPage from './ObservabilityPage';
import * as apiClient from '../services/apiClient';

vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({
    currentUser: { uid: 'test_user', email: 'test@example.com' },
    userProfile: { role: 'admin', is_approved: true, is_admin: true },
    loading: false,
    isDevBypass: false,
  }),
}));

vi.mock('../services/apiClient', () => ({
  fetchGenerationRuns: vi.fn(),
  fetchTelemetryEvents: vi.fn(),
  fetchRequestTrace: vi.fn(),
  fetchTelemetryStats: vi.fn(),
  fetchSystemLogs: vi.fn(),
  fetchDatabaseSummary: vi.fn(),
  fetchDatabaseTableRecords: vi.fn(),
  resolveImageUrl: vi.fn((url) => url),
}));

describe('ObservabilityPage', () => {
  const mockRuns = [
    {
      request_id: 'req_test_123',
      timestamp: '2026-08-26T10:00:00Z',
      status: 'success',
      duration_ms: 2450.5,
      cost_usd: 0.042,
      tokens: 1250,
      models: ['gemini-3.7-flash', 'gemini-3.1-flash-image'],
      primary_model: 'gemini-3.7-flash',
      component: 'generation',
      components: ['vision', 'generation'],
      prompt: 'Cinematic portrait with rim light and editorial styling',
      step_count: 2,
      input_images: ['https://example.com/ref1.jpg'],
      output_images: ['https://example.com/out1.jpg'],
      events: [
        {
          id: 'ev_1',
          event: 'vision_analysis_completed',
          component: 'vision',
          duration_ms: 850,
          status: 'success',
        },
        {
          id: 'ev_2',
          event: 'baseline_generation_completed',
          component: 'generation',
          duration_ms: 1600.5,
          status: 'success',
        },
      ],
    },
  ];

  const mockEvents = [
    {
      id: 'ev_1',
      timestamp: '2026-08-26T10:00:00Z',
      event: 'fine_tune_request',
      event_type: 'fine_tune_request',
      request_id: 'req_test_123',
      component: 'generation',
      status: 'success',
      model: 'gemini-3.1-flash-image',
      duration_ms: 850.5,
      cost_usd: 0.02,
    },
    {
      id: 'ev_2',
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
    total_events: 10,
    error_count: 1,
    success_rate: 90.0,
    total_cost_usd: 0.245,
    total_tokens: 8500,
    components: { generation: 6, vision: 4 },
    event_types: { fine_tune_request: 5, vision_analysis: 5 },
    average_latencies_ms: { 'gemini-3.7-flash': 1200.0 },
  };

  const mockLogs = {
    total_lines: 2,
    logs: [
      '[INFO] [req:req_test_123] Generation pipeline started',
      '[INFO] [req:req_test_123] Image synthesized successfully',
    ],
  };

  const mockDbSummary = {
    generations: 12,
    telemetry_events: 55,
    users: 4,
  };

  const mockDbRows = {
    table: 'generations',
    total: 1,
    limit: 25,
    offset: 0,
    rows: [
      {
        id: 'gen_001',
        prompt: 'Cinematic portrait',
        created_at: '2026-08-26T10:00:00Z',
      },
    ],
  };

  beforeEach(() => {
    vi.clearAllMocks();
    apiClient.fetchGenerationRuns.mockResolvedValue({
      total: 1,
      limit: 30,
      offset: 0,
      runs: mockRuns,
    });
    apiClient.fetchTelemetryEvents.mockResolvedValue({
      total: 2,
      limit: 50,
      offset: 0,
      events: mockEvents,
    });
    apiClient.fetchTelemetryStats.mockResolvedValue(mockStats);
    apiClient.fetchSystemLogs.mockResolvedValue(mockLogs);
    apiClient.fetchDatabaseSummary.mockResolvedValue({ tables: mockDbSummary });
    apiClient.fetchDatabaseTableRecords.mockResolvedValue(mockDbRows);
    apiClient.fetchRequestTrace.mockResolvedValue(mockRuns[0].events);
  });

  it('renders header, global KPI strip, and default Pipeline Traces view', async () => {
    render(<ObservabilityPage />);

    expect(screen.getByText(/Studio Observability & System Intelligence/i)).toBeInTheDocument();
    expect(screen.getByText(/Studio Pipeline/i)).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getAllByText(/req_test_123/i).length).toBeGreaterThan(0);
      expect(screen.getAllByText(/Cinematic portrait with rim light/i).length).toBeGreaterThan(0);
    });

    expect(screen.getByText(/90%/i)).toBeInTheDocument();
    expect(screen.getByText(/Tokens Processed/i)).toBeInTheDocument();
    expect(screen.getByText(/8,500/i)).toBeInTheDocument();
  });

  it('allows switching to Audit Events tab and viewing event records', async () => {
    render(<ObservabilityPage />);

    const eventsTabBtn = screen.getByRole('button', { name: /Audit Events/i });
    fireEvent.click(eventsTabBtn);

    await waitFor(() => {
      expect(screen.getByText(/fine_tune_request/i)).toBeInTheDocument();
      expect(screen.getByText(/vision_error/i)).toBeInTheDocument();
    });
  });

  it('allows switching to System Logs tab and viewing live logs stream', async () => {
    render(<ObservabilityPage />);

    const logsTabBtn = screen.getByRole('button', { name: /System Logs/i });
    fireEvent.click(logsTabBtn);

    await waitFor(() => {
      expect(screen.getByText(/Generation pipeline started/i)).toBeInTheDocument();
      expect(screen.getByText(/Image synthesized successfully/i)).toBeInTheDocument();
    });
  });

  it('allows switching to Database Explorer tab and viewing collections', async () => {
    render(<ObservabilityPage />);

    const dbTabBtn = screen.getByRole('button', { name: /Database Explorer/i });
    fireEvent.click(dbTabBtn);

    await waitFor(() => {
      expect(screen.getAllByText(/generations/i).length).toBeGreaterThan(0);
      expect(screen.getByText('gen_001')).toBeInTheDocument();
    });
  });

  it('renders error banner when stats fails to load and allows retry', async () => {
    apiClient.fetchTelemetryStats.mockRejectedValue(new Error('Network connection timeout'));
    apiClient.fetchGenerationRuns.mockRejectedValue(new Error('Network connection timeout'));
    render(<ObservabilityPage />);

    await waitFor(() => {
      expect(screen.getByText(/Network connection timeout/i)).toBeInTheDocument();
    });

    const retryBtn = screen.getByRole('button', { name: /Retry/i });
    expect(retryBtn).toBeInTheDocument();
  });
});
