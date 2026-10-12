import { File } from 'expo-file-system';

import type { MessageResponse } from './types';

/**
 * Authenticated-request executor supplied by ApiClient — the functions here own
 * the /api/v1/messages wire shape; the client owns bearer + refresh-on-401.
 */
export type AuthedRequest = (path: string, init: RequestInit) => Promise<MessageResponse>;

export interface SendMessageInput {
  text: string;
}

export interface AudioMessageInput {
  /** Local URI of the recording (expo-audio `recorder.uri`). */
  uri: string;
  /** Becomes the multipart part's Content-Type; falls back to the file's own type. */
  mimeType?: string;
  /** Optional note the backend appends to the transcript, like a Telegram caption. */
  caption?: string;
}

const MESSAGES_PATH = '/api/v1/messages';

/** Typed meal logging — POST /api/v1/messages as JSON {text}. */
export function sendMessage(
  request: AuthedRequest,
  { text }: SendMessageInput,
): Promise<MessageResponse> {
  return request(MESSAGES_PATH, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({ text }),
  });
}

/**
 * Voice note meal logging — POST /api/v1/messages as multipart with the
 * recording in the `audio` field (plus optional `caption`). Serialized by
 * the Expo fetch runtime installed as the global fetch; RN's stock fetch
 * cannot send File/Blob form parts.
 */
export async function sendAudioMessage(
  request: AuthedRequest,
  { uri, mimeType, caption }: AudioMessageInput,
): Promise<MessageResponse> {
  const file = new File(uri);
  const audio = new Blob([await file.arrayBuffer()], {
    type: mimeType || file.type || 'audio/m4a',
  });
  const filename = file.name || 'voice.m4a';
  // `name` also becomes the part filename on the stock RN FormData path,
  // which ignores the third append argument but reads a `name` property.
  (audio as Blob & { name?: string }).name = filename;

  const form = new FormData();
  form.append('audio', audio, filename);
  const trimmedCaption = caption?.trim();
  if (trimmedCaption) form.append('caption', trimmedCaption);

  return request(MESSAGES_PATH, { method: 'POST', body: form });
}
