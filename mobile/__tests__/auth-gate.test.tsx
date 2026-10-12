import { render, screen } from '@testing-library/react-native';
import { Text } from 'react-native';

import { AuthGate, redirectFor } from '../src/auth/AuthGate';
import { useAuth, type AuthContextValue } from '../src/auth/AuthContext';

const mockReplace = jest.fn();

jest.mock('expo-router', () => ({
  useSegments: jest.fn(),
  useRouter: () => ({ replace: mockReplace }),
}));

jest.mock('../src/auth/AuthContext', () => ({
  useAuth: jest.fn(),
}));

const mockedUseAuth = jest.mocked(useAuth);
const mockedUseSegments = jest.mocked(jest.requireMock('expo-router').useSegments) as jest.Mock;

function authWith(status: AuthContextValue['status']): AuthContextValue {
  return { status } as AuthContextValue;
}

beforeEach(() => {
  mockReplace.mockClear();
  mockedUseAuth.mockReset();
  mockedUseSegments.mockReset();
});

describe('redirectFor', () => {
  it('sends unauthenticated users outside the auth group to login', () => {
    expect(redirectFor('unauthenticated', false)).toBe('/(auth)/login');
  });

  it('sends authenticated users inside the auth group home', () => {
    expect(redirectFor('authenticated', true)).toBe('/');
  });

  it('does not redirect when already on the right side of the gate', () => {
    expect(redirectFor('unauthenticated', true)).toBeNull();
    expect(redirectFor('authenticated', false)).toBeNull();
  });

  it('never redirects while the session is still loading', () => {
    expect(redirectFor('loading', false)).toBeNull();
    expect(redirectFor('loading', true)).toBeNull();
  });
});

describe('AuthGate', () => {
  it('shows a loading state and does not redirect while restoring the session', async () => {
    mockedUseAuth.mockReturnValue(authWith('loading'));
    mockedUseSegments.mockReturnValue(['index']);

    await render(<AuthGate><Text>app</Text></AuthGate>);

    expect(screen.getByTestId('auth-loading')).toBeOnTheScreen();
    expect(mockReplace).not.toHaveBeenCalled();
  });

  it('redirects an unauthenticated user to login', async () => {
    mockedUseAuth.mockReturnValue(authWith('unauthenticated'));
    mockedUseSegments.mockReturnValue(['index']);

    await render(<AuthGate><Text>app</Text></AuthGate>);

    expect(mockReplace).toHaveBeenCalledWith('/(auth)/login');
  });

  it('redirects an authenticated user out of the auth group', async () => {
    mockedUseAuth.mockReturnValue(authWith('authenticated'));
    mockedUseSegments.mockReturnValue(['(auth)', 'login']);

    await render(<AuthGate><Text>app</Text></AuthGate>);

    expect(mockReplace).toHaveBeenCalledWith('/');
  });

  it('leaves an authenticated user alone on a protected route', async () => {
    mockedUseAuth.mockReturnValue(authWith('authenticated'));
    mockedUseSegments.mockReturnValue(['index']);

    await render(<AuthGate><Text>app</Text></AuthGate>);

    expect(mockReplace).not.toHaveBeenCalled();
  });
});
