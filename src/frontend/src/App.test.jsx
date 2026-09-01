import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import App from './App';
import * as AuthContextModule from './contexts/AuthContext';

describe('App Component Workflow & Locking', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ generations: [] }),
    }));
  });

  it('locks the app behind AuthPortal when user is unauthenticated', () => {
    vi.spyOn(AuthContextModule, 'useAuth').mockReturnValue({
      currentUser: null,
      userProfile: null,
      loading: false,
      signOutUser: vi.fn(),
      signInWithGoogle: vi.fn(),
      signInWithEmail: vi.fn(),
      signUpWithEmail: vi.fn(),
      quickDevLogin: vi.fn(),
      refreshUserProfile: vi.fn(),
    });

    render(<App />);
    expect(screen.getByText('Fashion Art Director')).toBeInTheDocument();
    expect(screen.getByText(/Continue with Google/i)).toBeInTheDocument();
    expect(screen.queryByText('Fashion AI')).not.toBeInTheDocument();
  });

  it('renders Step 1 Art Direction layout when user is authenticated & approved', () => {
    vi.spyOn(AuthContextModule, 'useAuth').mockReturnValue({
      currentUser: { uid: 'user_123', email: 'director@fashion.com', displayName: 'Fashion Director' },
      userProfile: {
        id: 'user_123',
        uid: 'user_123',
        email: 'director@fashion.com',
        display_name: 'Fashion Director',
        role: 'admin',
        status: 'approved',
        is_approved: true,
        is_admin: true,
      },
      loading: false,
      signOutUser: vi.fn(),
      signInWithGoogle: vi.fn(),
      signInWithEmail: vi.fn(),
      signUpWithEmail: vi.fn(),
      quickDevLogin: vi.fn(),
      refreshUserProfile: vi.fn(),
    });

    render(<App />);
    expect(screen.getByText('Fashion AI')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /1 Art Direction/i })).toBeInTheDocument();
    expect(screen.getByText(/Moodboard Ingestion/i)).toBeInTheDocument();
    expect(screen.getByText(/Direct Photo Ingestion/i)).toBeInTheDocument();
    expect(screen.getByTitle(/Studio Whitelist & Team Management/i)).toBeInTheDocument();
  });

  it('opens History Drawer when history button is clicked', async () => {
    vi.spyOn(AuthContextModule, 'useAuth').mockReturnValue({
      currentUser: { uid: 'user_123', email: 'director@fashion.com', displayName: 'Fashion Director' },
      userProfile: {
        id: 'user_123',
        uid: 'user_123',
        email: 'director@fashion.com',
        role: 'user',
        status: 'approved',
        is_approved: true,
        is_admin: false,
      },
      loading: false,
      signOutUser: vi.fn(),
      signInWithGoogle: vi.fn(),
      signInWithEmail: vi.fn(),
      signUpWithEmail: vi.fn(),
      quickDevLogin: vi.fn(),
      refreshUserProfile: vi.fn(),
    });

    render(<App />);

    const historyBtn = screen.getByRole('button', { name: /Lineage History/i });
    fireEvent.click(historyBtn);

    expect(screen.getByText(/Generation Lineage & History/i)).toBeInTheDocument();
  });
});
