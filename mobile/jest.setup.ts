// Native modules with no JS implementation under jest. Tests that exercise
// storage or device-id code do so through injected fakes; these mocks are a
// safety net so an accidental import can never touch a native binding.
jest.mock('expo-secure-store', () => ({
  getItemAsync: jest.fn(async () => null),
  setItemAsync: jest.fn(async () => undefined),
  deleteItemAsync: jest.fn(async () => undefined),
}));

jest.mock('expo-crypto', () => ({
  randomUUID: jest.fn(async () => 'test-device-id'),
}));

jest.mock('expo-file-system', () => ({
  File: jest.fn().mockImplementation((uri: string) => ({
    uri,
    name: uri.split('/').pop() ?? 'voice.m4a',
    type: 'audio/m4a',
    arrayBuffer: async () => new ArrayBuffer(8),
  })),
}));
