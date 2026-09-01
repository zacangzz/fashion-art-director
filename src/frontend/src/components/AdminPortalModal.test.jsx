import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import AdminPortalModal from './AdminPortalModal';
import * as apiClient from '../services/apiClient';

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

  beforeEach(() => {
    vi.spyOn(apiClient, 'fetchAdminUsersList').mockResolvedValue({
      users: mockUsers,
      summary: {
        total_users: 2,
        approved_count: 1,
        pending_count: 1,
        disabled_count: 0,
        total_spend_usd: 12.5,
      },
    });
  });

  it('renders admin whitelist modal with summary stats and user table', async () => {
    render(<AdminPortalModal isOpen={true} onClose={vi.fn()} />);

    expect(screen.getByText('Studio Whitelist & Team Management')).toBeInTheDocument();
    
    await waitFor(() => {
      expect(screen.getByText('director@fashionstudio.com')).toBeInTheDocument();
      expect(screen.getByText('designer@fashionstudio.com')).toBeInTheDocument();
    });

    expect(screen.getAllByText('$12.50').length).toBeGreaterThanOrEqual(1);
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
});
