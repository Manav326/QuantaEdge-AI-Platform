# Cloudflare Tunnel on the AI laptop (Windows)

The tunnel connector runs natively on the AI laptop, not in Docker. It forwards the public hostname `ai-api.quantaedge.in` to the local FastAPI gateway at `http://localhost:8000`.

## Prerequisites

- A domain zone `quantaedge.in` managed in the Cloudflare account.
- The native Windows FastAPI service listening on `127.0.0.1:8000`.
- Cloudflare account authorization by an administrator.

## Install cloudflared

```powershell
winget install --id Cloudflare.cloudflared -e
```

Open a new PowerShell window and authenticate:

```powershell
cloudflared tunnel login
cloudflared tunnel create quantaedge-ai
cloudflared tunnel route dns quantaedge-ai ai-api.quantaedge.in
```

Cloudflare returns a tunnel UUID and creates a credentials JSON file under `%USERPROFILE%\.cloudflared`. Keep that JSON private; do not commit it.

## Tunnel configuration

Create `%USERPROFILE%\.cloudflared\config.yml` using the UUID and credentials file path returned above:

```yaml
tunnel: REPLACE_WITH_TUNNEL_UUID
credentials-file: C:\Users\REPLACE_WITH_WINDOWS_USER\.cloudflared\REPLACE_WITH_TUNNEL_UUID.json

ingress:
  - hostname: ai-api.quantaedge.in
    service: http://localhost:8000
  - service: http_status:404
```

Validate and run:

```powershell
cloudflared tunnel ingress validate
cloudflared tunnel run quantaedge-ai
```

Once verified, install `cloudflared` as a Windows service using the official Cloudflare Windows service instructions. Protect the hostname with a Cloudflare Access service-auth policy for approved application backend callers. Keep FastAPI API-key authentication enabled as a second layer.

## Security rules

- Do not tunnel port 11434 (Ollama), 5432 (PostgreSQL) or 6379 (Redis).
- Do not publish the API on `0.0.0.0`; Uvicorn binds natively to `127.0.0.1:8000` on Windows.
- Do not commit tunnel credentials, certificates or tokens.
- Laptop sleep, shutdown or internet loss makes the API unavailable. Production uptime requires an always-on host.
