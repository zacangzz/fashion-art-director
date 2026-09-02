import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import ProxyBanner from './ProxyBanner';
import * as AuthContextModule from '../contexts/AuthContext';

describe('ProxyBanner Component', () => {
  it('renders nothing when not in proxy mode', () => {
    vi.spyOn(AuthContextModule, 'useAuth').mockReturnValue({
      userProfile: { is_proxy: false },
      stopProxy: vi.fn(),
    });

    const { container } = render(<ProxyBanner onOpenAdminModal={vi.fn()} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders proxy HUD details when is_proxy is true', () => {
    const mockStopProxy = vi.fn();
    const mockOpenModal = vi.fn();

    vi.spyOn(AuthContextModule, 'useAuth').mockReturnValue({
      userProfile: {
        id: 'target_123',
        email: 'designer@fashionstudio.com',
        display_name: 'Senior Designer',
        role: 'user',
        total_spend_usd: 5.5,
        total_spend_sgd: 7.425,
        is_proxy: true,
        proxied_by: {
          email: 'admin@fashionstudio.com',
        },
      },
      stopProxy: mockStopProxy,
    });

    render(<ProxyBanner onOpenAdminModal={mockOpenModal} />);

    expect(screen.getByText(/PROXY SESSION ACTIVE/i)).toBeInTheDocument();
    expect(screen.getByText('Senior Designer')).toBeInTheDocument();
    expect(screen.getByText(/Role: user/i)).toBeInTheDocument();
    expect(screen.getByText(/Authenticated Admin: admin@fashionstudio.com/i)).toBeInTheDocument();

    // Click Exit Proxy
    const exitBtn = screen.getByRole('button', { name: /Exit Proxy/i });
    fireEvent.click(exitBtn);
    expect(mockStopProxy).toHaveBeenCalledTimes(1);

    // Click Switch User
    const switchBtn = screen.getByRole('button', { name: /Switch User/i });
    fireEvent.click(switchBtn);
    expect(mockOpenModal).toHaveBeenCalledTimes(1);
  });
});
