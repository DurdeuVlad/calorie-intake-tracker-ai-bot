import { fireEvent, render, screen, waitFor } from '@testing-library/react-native';
import { Alert } from 'react-native';

import MemoriesScreen from '../src/app/memories';
import { useAuth } from '../src/auth/AuthContext';

jest.mock('expo-router', () => ({
  router: { back: jest.fn() },
}));

jest.mock('../src/auth/AuthContext', () => ({
  useAuth: jest.fn(),
}));

const mockedUseAuth = jest.mocked(useAuth);

const listMemories = jest.fn();
const deleteMemory = jest.fn();

const MEMORIES = [
  {
    id: 1,
    kind: 'preference',
    text: 'prefers Romanian',
    source: 'agent',
    created_at: '2026-10-10T09:30:00Z',
    updated_at: '2026-10-10T09:30:00Z',
  },
  {
    id: 2,
    kind: 'restriction',
    text: 'no dairy',
    source: 'user',
    created_at: '2026-10-11T18:00:00Z',
    updated_at: '2026-10-11T18:00:00Z',
  },
];

function alertButtons(): { text?: string; onPress?: () => void; style?: string }[] {
  const calls = jest.mocked(Alert.alert).mock.calls;
  const last = calls[calls.length - 1];
  return (last?.[2] ?? []) as { text?: string; onPress?: () => void; style?: string }[];
}

beforeEach(() => {
  jest.clearAllMocks();
  mockedUseAuth.mockReturnValue({ client: { listMemories, deleteMemory } } as never);
});

describe('MemoriesScreen', () => {
  it('lists each saved fact with kind, source, and created date', async () => {
    listMemories.mockResolvedValue({ memories: MEMORIES });
    await render(<MemoriesScreen />);

    expect(await screen.findByTestId('memory-1')).toBeOnTheScreen();
    expect(screen.getByTestId('memory-2')).toBeOnTheScreen();
    expect(screen.getByText('prefers Romanian')).toBeOnTheScreen();
    expect(screen.getByText(/preference · agent · /)).toBeOnTheScreen();
    expect(screen.getByText(/restriction · user · /)).toBeOnTheScreen();
  });

  it('shows the empty-state copy when nothing is saved', async () => {
    listMemories.mockResolvedValue({ memories: [] });
    await render(<MemoriesScreen />);

    expect(await screen.findByTestId('memories-empty')).toHaveTextContent(
      /agent saves facts it learns about you/,
    );
  });

  it('asks for confirmation before deleting and does not delete on cancel', async () => {
    listMemories.mockResolvedValue({ memories: MEMORIES });
    const alertSpy = jest.spyOn(Alert, 'alert');
    await render(<MemoriesScreen />);
    await screen.findByTestId('memory-1');

    await fireEvent.press(screen.getByTestId('delete-memory-1'));

    expect(alertSpy).toHaveBeenCalledTimes(1);
    const [title, message] = jest.mocked(Alert.alert).mock.calls[0];
    expect(title).toBe('Delete this memory?');
    expect(message).toBe('prefers Romanian');

    // Nothing is deleted until the destructive button is pressed.
    expect(deleteMemory).not.toHaveBeenCalled();
    expect(screen.getByTestId('memory-1')).toBeOnTheScreen();
  });

  it('deletes through the client and removes the row when confirmed', async () => {
    listMemories.mockResolvedValue({ memories: MEMORIES });
    deleteMemory.mockResolvedValue(undefined);
    jest.spyOn(Alert, 'alert');
    await render(<MemoriesScreen />);
    await screen.findByTestId('memory-1');

    await fireEvent.press(screen.getByTestId('delete-memory-1'));
    const destructive = alertButtons().find((b) => b.style === 'destructive');
    expect(destructive?.text).toBe('Delete');
    await waitFor(async () => destructive!.onPress!());

    await waitFor(() => expect(deleteMemory).toHaveBeenCalledWith(1));
    await waitFor(() => expect(screen.queryByTestId('memory-1')).toBeNull());
    expect(screen.getByTestId('memory-2')).toBeOnTheScreen();
  });

  it('keeps the row when the delete call fails', async () => {
    listMemories.mockResolvedValue({ memories: MEMORIES });
    deleteMemory.mockRejectedValue(new Error('server down'));
    jest.spyOn(Alert, 'alert');
    await render(<MemoriesScreen />);
    await screen.findByTestId('memory-1');

    await fireEvent.press(screen.getByTestId('delete-memory-1'));
    const destructive = alertButtons().find((b) => b.style === 'destructive');
    await waitFor(async () => destructive!.onPress!());

    await waitFor(() => expect(deleteMemory).toHaveBeenCalledWith(1));
    expect(screen.getByTestId('memory-1')).toBeOnTheScreen();
  });
});
