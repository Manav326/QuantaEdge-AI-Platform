from app.security import ClientPrincipal


def test_client_principal_scopes_are_explicit():
    principal = ClientPrincipal(client_id="qe-backend", scopes=frozenset({"chat", "learning"}))
    assert "chat" in principal.scopes
    assert "admin:read" not in principal.scopes
