import { fireEvent, render, screen, waitFor } from '@testing-library/react-native';
import {
  requestRecordingPermissionsAsync,
  useAudioRecorder,
} from 'expo-audio';

import LogScreen from '../src/app/log';
import { useAuth } from '../src/auth/AuthContext';

jest.mock('expo-audio', () => {
  // One shared recorder — the screen holds the instance from first render in
  // its callbacks, so a re-render must return the same object.
  const recorder = {
    prepareToRecordAsync: jest.fn(async () => undefined),
    record: jest.fn(),
    stop: jest.fn(async () => undefined),
    uri: 'file:///cache/voice-1.m4a',
  };
  return {
    useAudioRecorder: jest.fn(() => recorder),
    useAudioRecorderState: jest.fn(() => ({
      isRecording: false,
      durationMillis: 0,
      canRecord: true,
    })),
    requestRecordingPermissionsAsync: jest.fn(async () => ({ granted: true })),
    setAudioModeAsync: jest.fn(async () => undefined),
    RecordingPresets: { HIGH_QUALITY: { extension: '.m4a' } },
  };
});

jest.mock('../src/auth/AuthContext', () => ({
  useAuth: jest.fn(),
}));

const mockedUseAuth = jest.mocked(useAuth);
const mockedPermission = jest.mocked(requestRecordingPermissionsAsync);
const mockedUseAudioRecorder = jest.mocked(useAudioRecorder);

const sendMessage = jest.fn();
const sendAudioMessage = jest.fn();

const RESPONSE = {
  reply: 'Logged: two eggs and a slice of toast.',
  actions: [
    {
      ok: true,
      type: 'ADD_ENTRY',
      entry: { id: 7, calories: 230, eaten_at: null, description: 'two eggs and toast' },
      date: '2026-10-12',
      message: null,
    },
  ],
};

function latestRecorder() {
  const results = mockedUseAudioRecorder.mock.results;
  return results[results.length - 1].value;
}

beforeEach(() => {
  jest.clearAllMocks();
  mockedPermission.mockResolvedValue({ granted: true } as never);
  mockedUseAuth.mockReturnValue({ client: { sendMessage, sendAudioMessage } } as never);
});

describe('LogScreen voice logging', () => {
  it('shows the permission-denied hint and never records when mic access is denied', async () => {
    mockedPermission.mockResolvedValue({ granted: false } as never);
    await render(<LogScreen />);

    const mic = screen.getByTestId('mic-button');
    await fireEvent(mic, 'pressIn');

    expect(await screen.findByTestId('mic-denied')).toBeOnTheScreen();
    expect(latestRecorder().prepareToRecordAsync).not.toHaveBeenCalled();
    expect(latestRecorder().record).not.toHaveBeenCalled();

    // Releasing after a denied press must not send anything.
    await fireEvent(mic, 'pressOut');
    expect(sendAudioMessage).not.toHaveBeenCalled();
    expect(sendMessage).not.toHaveBeenCalled();
  });

  it('records while held and uploads the note on release', async () => {
    sendAudioMessage.mockResolvedValue(RESPONSE);
    await render(<LogScreen />);

    const mic = screen.getByTestId('mic-button');
    await fireEvent(mic, 'pressIn');
    const recorder = latestRecorder();
    await waitFor(() => expect(recorder.record).toHaveBeenCalled());
    expect(recorder.prepareToRecordAsync).toHaveBeenCalled();

    await fireEvent(mic, 'pressOut');
    await waitFor(() =>
      expect(sendAudioMessage).toHaveBeenCalledWith({
        uri: 'file:///cache/voice-1.m4a',
        mimeType: 'audio/m4a',
      }),
    );
    expect(recorder.stop).toHaveBeenCalled();

    expect(await screen.findByTestId('agent-reply')).toHaveTextContent(
      'Logged: two eggs and a slice of toast.',
    );
    expect(screen.getByTestId('confirmation-card')).toBeOnTheScreen();
    expect(screen.getByText('two eggs and toast')).toBeOnTheScreen();
    expect(screen.getByText(/230 kcal/)).toBeOnTheScreen();
    expect(screen.getByTestId('confirmed-badge')).toHaveTextContent(/Confirmed by the app/);
  });
});

describe('LogScreen text logging', () => {
  it('sends the typed text and renders reply plus confirmation card', async () => {
    sendMessage.mockResolvedValue(RESPONSE);
    await render(<LogScreen />);

    await fireEvent.changeText(screen.getByTestId('text-input'), '  ovăz cu lapte  ');
    await fireEvent.press(screen.getByTestId('send-text-button'));

    await waitFor(() => expect(sendMessage).toHaveBeenCalledWith('ovăz cu lapte'));
    expect(await screen.findByTestId('agent-reply')).toBeOnTheScreen();
    expect(screen.getByTestId('confirmation-card')).toBeOnTheScreen();
    // Cleared after a successful send.
    expect(screen.getByTestId('text-input').props.value).toBe('');
  });

  it('surfaces the mapped error when the send fails', async () => {
    sendMessage.mockRejectedValue(new Error('network down'));
    await render(<LogScreen />);

    await fireEvent.changeText(screen.getByTestId('text-input'), 'salată');
    await fireEvent.press(screen.getByTestId('send-text-button'));

    expect(await screen.findByTestId('send-error')).toHaveTextContent(
      'Could not reach the server. Check your connection and try again.',
    );
  });
});
