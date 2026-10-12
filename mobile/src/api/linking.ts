import type {
  AuthedRequest,
  LinkIssueResponse,
  LinkRedeemRequest,
  LinkStatusResponse,
} from './types';

/**
 * /api/v1/link — the mobile half of cross-surface account linking
 * (python-app/app/mobile/linking.py). /issue mints the 8-char, 10-min code
 * the user types into the Telegram bot; /redeem consumes a bot-issued code.
 */

const LINK_PATH = '/api/v1/link';

const JSON_HEADERS = {
  'Content-Type': 'application/json',
  Accept: 'application/json',
};

/** GET /api/v1/link/status — messaging providers sharing this account's journal. */
export function linkStatus(request: AuthedRequest): Promise<LinkStatusResponse> {
  return request<LinkStatusResponse>(`${LINK_PATH}/status`, { method: 'GET' });
}

/** POST /api/v1/link/issue — mint a code to type as "link CODE" in Telegram. */
export function issueLinkCode(request: AuthedRequest): Promise<LinkIssueResponse> {
  return request<LinkIssueResponse>(`${LINK_PATH}/issue`, {
    method: 'POST',
    headers: JSON_HEADERS,
  });
}

/**
 * POST /api/v1/link/redeem — consume a code the Telegram bot issued.
 * 400 = invalid/expired code; 409 = this account already has journal data.
 */
export function redeemLinkCode(
  request: AuthedRequest,
  code: string,
): Promise<LinkStatusResponse> {
  const body: LinkRedeemRequest = { code };
  return request<LinkStatusResponse>(`${LINK_PATH}/redeem`, {
    method: 'POST',
    headers: JSON_HEADERS,
    body: JSON.stringify(body),
  });
}
