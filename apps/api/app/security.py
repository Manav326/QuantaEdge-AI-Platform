import hmac
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from app.core.settings import get_settings
from app.core.layers import get_layers


@dataclass(frozen=True)
class ClientPrincipal:
    client_id: str
    scopes: frozenset[str]


def _extract_api_key(x_api_key: str | None, authorization: str | None) -> str | None:
    """Accept existing X-API-Key clients and standard Bearer-auth clients."""
    bearer_key = None
    if authorization:
        scheme, separator, credentials = authorization.partition(" ")
        if separator and scheme.lower() == "bearer" and credentials.strip():
            bearer_key = credentials.strip()
    if x_api_key and bearer_key and not hmac.compare_digest(x_api_key, bearer_key):
        return None
    return bearer_key or x_api_key


async def authenticate_client(
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> ClientPrincipal:
    settings = get_settings()
    if not settings.api_keys:
        raise HTTPException(status_code=503, detail="API authentication is not configured")
    minimum_length = int(get_layers().layer("security")["authentication"].get("minimum_key_length", 32))
    valid_records = {
        client_id: record
        for client_id, record in settings.api_keys.items()
        if isinstance(record, dict) and len(str(record.get("key", ""))) >= minimum_length
    }
    if not valid_records:
        raise HTTPException(status_code=503, detail="No sufficiently strong API credentials are configured")
    supplied_key = _extract_api_key(x_api_key, authorization)
    if not supplied_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing or invalid API key")

    for client_id, record in valid_records.items():
        expected = str(record.get("key", ""))
        if hmac.compare_digest(supplied_key, expected):
            scopes = record.get("scopes", [])
            if not isinstance(scopes, list):
                scopes = []
            return ClientPrincipal(client_id=client_id, scopes=frozenset(str(item) for item in scopes))

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")


def require_scope(scope: str):
    async def dependency(principal: Annotated[ClientPrincipal, Depends(authenticate_client)]) -> ClientPrincipal:
        if "*" not in principal.scopes and scope not in principal.scopes:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="API key lacks required scope")
        return principal

    return dependency
