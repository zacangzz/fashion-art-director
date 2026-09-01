import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import AuthPortal from './AuthPortal';
import * as AuthContextModule from '../contexts/AuthContext';

describe('AuthPortal Component', () => {
  it('renders login portal with Google and Email sign-in', () => {
    vi.spyOn(AuthContextModule, 'useAuth').mockReturnValue({
      currentUser: null,
      userProfile: null,
      loading: false,
      signInWithGoogle: vi.fn(),
      signInWithEmail: vi.fn(),
      signUpWithEmail: vi.fn(),
      signOutUser: vi.fn(),
      quickDevLogin: vi.fn(),
      refreshUserProfile: vi.fn(),
    });

    render(<AuthPortal />);

    expect(screen.getByText('Fashion Art Director')).toBeInTheDocument();
    expect(screen.getByText(/Continue with Google/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText('director@fashionstudio.com')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Sign In to Studio/i })).toBeInTheDocument();
    expect(screen.getByText(/Developer Quick Access/i)).toBeInTheDocument();
  });

  it('toggles between Sign In and Create Account form', () => {
    vi.spyOn(AuthContextModule, 'useAuth').mockReturnValue({
      currentUser: null,
      userProfile: null,
      loading: false,
      signInWithGoogle: vi.fn(),
      signInWithEmail: vi.fn(),
      signUpWithEmail: vi.fn(),
      signOutUser: vi.fn(),
      quickDevLogin: vi.fn(),
      refreshUserProfile: vi.fn(),
    });

    render(<AuthPortal />);

    const registerToggle = screen.getByRole('button', { name: /Register/i });
    fireEvent.click(registerToggle);

    expect(screen.getByRole('button', { name: /Create Studio Account/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Sign In/i })).toBeInTheDocument();
  });

  it('renders Restricted view when user is authenticated but not approved', () => {
    vi.spyOn(AuthContextModule, 'useAuth').mockReturnValue({
      currentUser: { email: 'unauthorized@example.com', uid: 'user_unauth' },
      userProfile: { status: 'unauthorized', is_approved: false },
      loading: false,
      signInWithGoogle: vi.fn(),
      signInWithEmail: vi.fn(),
      signUpWithEmail: vi.fn(),
      signOutUser: vi.fn(),
      quickDevLogin: vi.fn(),
      refreshUserProfile: vi.fn(),
    });

    render(<AuthPortal />);

    expect(screen.getByText(/Studio Access Restricted/i)).toBeInTheDocument();
    expect(screen.getByText('unauthorized@example.com')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Check Approval Status/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Sign Out \/ Switch Account/i })).toBeInTheDocument();
  });
});
