from app.security import ClientPrincipal, _extract_api_key


def test_client_principal_scopes_are_explicit():
    principal = ClientPrincipal(client_id="qe-backend", scopes=frozenset({"chat", "learning"}))
    assert "chat" in principal.scopes
    assert "admin:read" not in principal.scopes


def test_api_auth_accepts_bearer_and_legacy_header():
    assert _extract_api_key(None, "Bearer secret-key") == "secret-key"
    assert _extract_api_key("legacy-key", None) == "legacy-key"


def test_api_auth_rejects_conflicting_auth_headers():
    assert _extract_api_key("key-one", "Bearer key-two") is None


def test_api_auth_ignores_non_bearer_authorization_scheme():
    assert _extract_api_key(None, "Basic dXNlcjpwYXNz") is None
