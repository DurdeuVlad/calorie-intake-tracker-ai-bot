// Runtime config extras. app.json holds the static manifest; this layer only
// injects values that differ per environment. The FastAPI base URL is read
// from app config `extra` by src/api/config.ts.
module.exports = ({ config }) => ({
  ...config,
  extra: {
    ...config.extra,
    apiBaseUrl: process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8000',
  },
});
