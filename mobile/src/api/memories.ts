import type { AuthedRequest, MemoryListResponse } from './types';

/**
 * /api/v1/memories — the durable facts the agent saved about the user
 * (python-app/app/mobile/memories.py). Deletes are soft server-side.
 */

const MEMORIES_PATH = '/api/v1/memories';

/** GET /api/v1/memories — every active memory for the account. */
export function listMemories(request: AuthedRequest): Promise<MemoryListResponse> {
  return request<MemoryListResponse>(MEMORIES_PATH, { method: 'GET' });
}

/** DELETE /api/v1/memories/{id} — 204 on success, 404 when already gone. */
export function deleteMemory(request: AuthedRequest, memoryId: number): Promise<void> {
  return request<void>(`${MEMORIES_PATH}/${memoryId}`, { method: 'DELETE' });
}
