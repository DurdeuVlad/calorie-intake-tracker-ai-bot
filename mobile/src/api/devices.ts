import type {
  AuthedRequest,
  DeviceListResponse,
  DeviceRegisterInput,
  DeviceResponse,
} from './types';

/**
 * /api/v1/devices — push-token registry (python-app/app/mobile/devices.py).
 * POST upserts on (account_id, push_token); DELETE disables pushes (soft).
 */

const DEVICES_PATH = '/api/v1/devices';

const JSON_HEADERS = {
  'Content-Type': 'application/json',
  Accept: 'application/json',
};

/** POST /api/v1/devices — register or refresh this install's push token. */
export function registerDevice(
  request: AuthedRequest,
  input: DeviceRegisterInput,
): Promise<DeviceResponse> {
  return request<DeviceResponse>(DEVICES_PATH, {
    method: 'POST',
    headers: JSON_HEADERS,
    body: JSON.stringify(input),
  });
}

/** GET /api/v1/devices — every device row for the account. */
export function listDevices(request: AuthedRequest): Promise<DeviceListResponse> {
  return request<DeviceListResponse>(DEVICES_PATH, { method: 'GET' });
}

/** DELETE /api/v1/devices/{id} — disable pushes for one device; 204 on success. */
export function disableDevice(request: AuthedRequest, deviceId: number): Promise<void> {
  return request<void>(`${DEVICES_PATH}/${deviceId}`, { method: 'DELETE' });
}
