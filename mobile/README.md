# mobile — Calorie Tracker React Native client

Expo-managed React Native app (SDK 57) for the FastAPI mobile surface in
`python-app/app/mobile/`. One codebase targets iOS and Android; the managed
workflow is never ejected — native escape hatches (Screen Time bridge, app
blocker, voice recorder per `docs/MISSION_AUDIT.md` §4.6–4.7) will land as
config plugins / dev-client modules later, not via eject.

## Stack decisions

- **Navigation: expo-router (file-based).** Chosen over React Navigation
  because it is the convention of the SDK's own templates (`src/app/` routes,
  `main: "expo-router/entry"`), gives deep-linking + the `(auth)` route-group
  gate for free, and React Navigation remains available underneath it for any
  screen that ever needs a custom navigator.
- **Tokens: `expo-secure-store`** (Keychain / EncryptedSharedPreferences).
  Never AsyncStorage — refresh tokens are bearer credentials.
- **API client: `fetch`, no third-party HTTP library.** The surface is four
  endpoints; the wrapper owns auth headers, refresh-on-401 retry, and error
  normalization.

## Layout

```
src/app/            expo-router routes (every file = a screen)
  _layout.tsx       AuthProvider + AuthGate + Stack
  (auth)/           unauthenticated group: login.tsx, signup.tsx
  index.tsx         home — account email + linkedProviders
src/api/            typed client for /api/v1/* (client.ts), wire types (types.ts),
                    ApiError/AuthError (errors.ts), base URL (config.ts),
                    composition root (index.ts)
src/auth/           SessionStore port + SecureStore impl (storage.ts),
                    AuthContext state (AuthContext.tsx), route gate (AuthGate.tsx),
                    form rules mirrored from the server (validation.ts)
src/components/     AuthForm (shared login/signup form)
__tests__/          jest + @testing-library/react-native
```

## API surface covered

| Method | Path | Client call |
| --- | --- | --- |
| POST | `/api/v1/auth/signup` | `client.signup(email, password)` |
| POST | `/api/v1/auth/login` | `client.login(email, password)` |
| POST | `/api/v1/auth/refresh` | internal — on 401, retried request once |
| GET | `/api/v1/link/status` | `client.getLinkStatus()` |
| POST | `/api/v1/messages` (JSON `{text}`) | `client.sendMessage(text)` |
| POST | `/api/v1/messages` (multipart `audio` + optional `caption`) | `client.sendAudioMessage({uri, mimeType, caption?})` |

Auth requests send `{email, password, device_id}`; `device_id` is a UUID
minted once and persisted in SecureStore (it survives sign-out — refresh
tokens are device-bound server-side). On a 401 the client exchanges the
refresh token once and retries once; a second 401 clears the session and
notifies `onSessionExpired`, which drops the app back to the login gate.
Concurrent 401s share a single in-flight refresh so rotation is never raced.

## Configuration

The base URL is read from app config `extra.apiBaseUrl` (`src/api/config.ts`),
set in `app.config.js` from `EXPO_PUBLIC_API_URL`, defaulting to
`http://localhost:8000`.

- iOS simulator: `http://localhost:8000` works as-is.
- Android emulator: `EXPO_PUBLIC_API_URL=http://10.0.2.2:8000 npx expo start`
  (10.0.2.2 is the emulator's alias for host loopback).
- Physical device: point it at the host's LAN IP, e.g.
  `EXPO_PUBLIC_API_URL=http://192.168.1.10:8000`.

## Commands

| Task | Command |
| --- | --- |
| Install deps | `npm install` |
| Dev server | `npx expo start` |
| Run on Android / iOS | `npm run android` / `npm run ios` |
| Typecheck | `npx tsc --noEmit` |
| Tests | `npx jest` |
| Dependency alignment | `npx expo install --check` |

Requires Node >= 20 (developed on Node 24). Dependency versions are pinned
exact and `.npmrc` sets `save-exact` + `legacy-peer-deps` (Expo's optional
web-only peers conflict under npm 11's stricter resolver and are unused for
an iOS/Android target).

## Testing notes

RNTL v14's API is async end-to-end: `await render(...)`, `await fireEvent.*`.
`jest.setup.ts` mocks `expo-secure-store`/`expo-crypto` as a safety net; API
client tests inject in-memory `SessionStore` + `fetch` fakes instead.
