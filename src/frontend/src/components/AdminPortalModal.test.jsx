import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import AdminPortalModal from './AdminPortalModal';
import * as apiClient from '../services/apiClient';
import * as AuthContextModule from '../contexts/AuthContext';

describe('AdminPortalModal Component', () => {
  const mockUsers = [
    {
      id: 'admin_1',
      email: 'director@fashionstudio.com',
      display_name: 'Fashion Director',
      role: 'admin',
      status: 'approved',
      total_spend_usd: 12.5,
      total_tokens: 25000,
    },
    {
      id: 'invite_designer@fashionstudio.com',
      email: 'designer@fashionstudio.com',
      display_name: 'designer',
      role: 'user',
      status: 'pending_invite',
      total_spend_usd: 0.0,
      total_tokens: 0,
    },
  ];

  const mockStartProxy = vi.fn();
  const mockStopProxy = vi.fn();

  beforeEach(() => {
    vi.spyOn(apiClient, 'fetchAdminUsersList').mockResolvedValue({
      users: mockUsers,
      summary: {
        total_users: 2,
        approved_count: 1,
        pending_count: 1,
        disabled_count: 0,
        total_spend_usd: 12.5,
        total_spend_sgd: 16.88,
      },
    });

    vi.spyOn(AuthContextModule, 'useAuth').mockReturnValue({
      userProfile: {
        id: 'admin_1',
        email: 'director@fashionstudio.com',
        role: 'admin',
        is_admin: true,
        is_proxy: false,
      },
      startProxy: mockStartProxy,
      stopProxy: mockStopProxy,
    });
  });

  it('renders admin whitelist modal with summary stats and user table', async () => {
    render(<AdminPortalModal isOpen={true} onClose={vi.fn()} />);

    expect(screen.getByText('Studio Whitelist & Team Management')).toBeInTheDocument();
    
    await waitFor(() => {
      expect(screen.getByText('director@fashionstudio.com')).toBeInTheDocument();
      expect(screen.getByText('designer@fashionstudio.com')).toBeInTheDocument();
    });

    expect(screen.getAllByText('S$16.88').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('You')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Act as User/i })).toBeInTheDocument();
  });

  it('submits pre-authorization invite form', async () => {
    const inviteSpy = vi.spyOn(apiClient, 'inviteUser').mockResolvedValue({
      status: 'success',
      message: 'Successfully pre-authorized newmember@studio.com.',
      user: { id: 'invite_new', email: 'newmember@studio.com', status: 'pending_invite' },
    });

    render(<AdminPortalModal isOpen={true} onClose={vi.fn()} />);

    const input = screen.getByPlaceholderText('designer@fashionstudio.com');
    fireEvent.change(input, { target: { value: 'newmember@studio.com' } });

    const submitBtn = screen.getByRole('button', { name: /Add to Whitelist/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(inviteSpy).toHaveBeenCalledWith('newmember@studio.com', 'user');
    });
  });

  it('triggers startProxy when Act as User button is clicked', async () => {
    const mockClose = vi.fn();
    render(<AdminPortalModal isOpen={true} onClose={mockClose} />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Act as User/i })).toBeInTheDocument();
    });

    const proxyBtn = screen.getByRole('button', { name: /Act as User/i });
    fireEvent.click(proxyBtn);

    expect(mockStartProxy).toHaveBeenCalledWith(mockUsers[1]);
    await waitFor(() => {
      expect(mockClose).toHaveBeenCalledTimes(1);
    });
  });
});
