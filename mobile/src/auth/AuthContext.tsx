import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';

import { createApiClient, sessionStore } from '../api';
import type { ApiClient } from '../api/client';
import { registerCurrentDevice } from '../devices/register';
import { normalizeEmail } from './validation';

export type AuthStatus = 'loading' | 'unauthenticated' | 'authenticated';

export interface AuthContextValue {
  status: AuthStatus;
  email: string | null;
  client: ApiClient;
  signIn(email: string, password: string): Promise<void>;
  signUp(email: string, password: string): Promise<void>;
  signOut(): Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<{ status: AuthStatus; email: string | null }>({
    status: 'loading',
    email: null,
  });

  const client = useMemo(
    () =>
      createApiClient({
        onSessionExpired: () => setState({ status: 'unauthenticated', email: null }),
      }),
    [],
  );

  useEffect(() => {
    let cancelled = false;
    void sessionStore.getSession().then((session) => {
      if (cancelled) return;
      setState(
        session
          ? { status: 'authenticated', email: session.email ?? null }
          : { status: 'unauthenticated', email: null },
      );
    });
    return () => {
      cancelled = true;
    };
  }, []);

  // Best-effort push registration on every authenticated transition (restored
  // session or fresh sign-in/sign-up). registerCurrentDevice swallows all
  // failures — it never affects auth state or the UI.
  useEffect(() => {
    if (state.status === 'authenticated') void registerCurrentDevice(client);
  }, [state.status, client]);

  const value = useMemo<AuthContextValue>(
    () => ({
      status: state.status,
      email: state.email,
      client,
      async signIn(email, password) {
        const normalized = normalizeEmail(email);
        await client.login(normalized, password);
        setState({ status: 'authenticated', email: normalized });
      },
      async signUp(email, password) {
        const normalized = normalizeEmail(email);
        await client.signup(normalized, password);
        setState({ status: 'authenticated', email: normalized });
      },
      async signOut() {
        await client.signOut();
        setState({ status: 'unauthenticated', email: null });
      },
    }),
    [client, state],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}
