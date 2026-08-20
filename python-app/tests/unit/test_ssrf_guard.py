"""isSafeExternalUrl() port -- reject non-http(s) schemes and any hostname that
resolves to a loopback/private/link-local/unspecified address. The multi-hop
redirect-chain walk (_resolve_safe_final_url) is exercised against a live
Browserless integration in Phase 6; this covers the single-URL check that
every hop of that walk depends on."""

from app.services.journal_tool_executor import JournalToolExecutor


def _executor() -> JournalToolExecutor:
    return JournalToolExecutor()


def test_rejects_non_http_schemes():
    executor = _executor()
    assert executor._is_safe_external_url("ftp://example.com/file") is False
    assert executor._is_safe_external_url("file:///etc/passwd") is False
    assert executor._is_safe_external_url("javascript:alert(1)") is False


def test_rejects_url_with_no_host():
    executor = _executor()
    assert executor._is_safe_external_url("https:///path") is False


def test_rejects_loopback_hostnames():
    executor = _executor()
    assert executor._is_safe_external_url("http://localhost/admin") is False
    assert executor._is_safe_external_url("http://127.0.0.1/admin") is False
    assert executor._is_safe_external_url("http://[::1]/admin") is False


def test_rejects_private_and_link_local_addresses():
    executor = _executor()
    assert executor._is_safe_external_url("http://10.0.0.5/") is False
    assert executor._is_safe_external_url("http://192.168.1.1/") is False
    assert executor._is_safe_external_url("http://169.254.169.254/latest/meta-data/") is False  # cloud metadata endpoint


def test_rejects_unspecified_address():
    executor = _executor()
    assert executor._is_safe_external_url("http://0.0.0.0/") is False


def test_accepts_a_normal_public_https_url():
    executor = _executor()
    assert executor._is_safe_external_url("https://example.com/page") is True


def test_rejects_malformed_url():
    executor = _executor()
    assert executor._is_safe_external_url("not a url at all") is False
