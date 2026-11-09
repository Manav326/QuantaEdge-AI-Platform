# Cloudflare Tunnel in Docker Desktop (Windows AI laptop)

This repository runs cloudflared as a Docker Desktop container. FastAPI remains a native Windows process listening only on 127.0.0.1:8000. Docker Desktop host networking lets the cloudflared container reach the Windows host's loopback address without widening the API listener or publishing port 8000.

## Prerequisites

- The quantaedge.in zone is active in the Cloudflare account.
- QuantaEdge FastAPI is running at http://127.0.0.1:8000.
- Docker Desktop uses Linux containers and is version 4.34 or later.
- Docker Desktop host networking is enabled in Settings → Resources → Network → Enable host networking. Apply the change and restart Docker Desktop.
- Enhanced Container Isolation is disabled. Docker Desktop host networking is incompatible with it.

Host networking shares the host network namespace with the cloudflared container. The connector can consequently reach other services bound to host loopback, not only FastAPI. The optional connector is defined in docker-compose.cloudflare.yml, drops all Linux capabilities, uses no-new-privileges and a read-only root filesystem. Do not run untrusted containers with host networking.

## 1. Create a remotely managed tunnel

1. In Cloudflare, create a remotely managed Cloudflared tunnel named quantaedge-ai-docker.
2. Select Docker and copy the tunnel token. Treat it as a password. Do not paste it into Git, chat, an image build, or a command line.
3. In Published application routes, add:

| Hostname | Service URL | Purpose |
|---|---|---|
| ai-api.quantaedge.in | http://127.0.0.1:8000 | QuantaEdge backend and approved server-side clients |
| harness-ai-api.quantaedge.in | http://127.0.0.1:8000 | Harness endpoint protected by Cloudflare Access |

Both routes use the same local API but distinct Access policies. Do not create routes to Ollama, PostgreSQL, Redis, Docker's API, or the Harness web UI.

## 2. Store the token locally and in a Docker-managed volume

Run from PowerShell:

~~~powershell
.\scripts\set-cloudflare-tunnel-token.ps1
~~~

Paste the token at the secure prompt. The script stores a protected local copy at D:\QuantaEdgeAI\secrets\cloudflare-tunnel.token, then transfers it through standard input into the Docker-managed volume quantaedge-cloudflare-tunnel-token. The token is not passed as a Docker argument or environment variable, and no Windows bind mount is used. The cloudflared container mounts the volume read-only at /run/secrets.

To replace a token after rotating it in Cloudflare, run the same script again. It overwrites the token in the Docker volume.

## 3. Start and verify the connector

Confirm Docker Desktop host networking is enabled, then run:

~~~powershell
.\scripts\start-cloudflared.ps1
docker compose -f docker-compose.yml -f docker-compose.cloudflare.yml ps cloudflared
docker compose -f docker-compose.yml -f docker-compose.cloudflare.yml logs --tail 60 cloudflared
~~~

In Cloudflare → Networking → Tunnels, the connector should show Healthy/Connected. The container has no published inbound ports; it establishes outbound connections to Cloudflare.

To stop it:

~~~powershell
docker compose -f docker-compose.yml -f docker-compose.cloudflare.yml stop cloudflared
~~~

## 4. Protect the Harness hostname separately

Create a Cloudflare Access Service Token named deepseek-harness-ai-laptop. Create a self-hosted Access application for harness-ai-api.quantaedge.in only and add a Service Auth policy containing this token. Do not apply the Harness-only policy to ai-api.quantaedge.in unless all existing callers also have Access tokens.

Requests to the Harness hostname must pass both Cloudflare Access service-token authentication and QuantaEdge Bearer API-key authentication. Keep both Access values private in the Harness profile configuration.

## 5. Verify the tunnel

After the dashboard shows the connector as Healthy:

~~~powershell
Resolve-DnsName ai-api.quantaedge.in
Resolve-DnsName harness-ai-api.quantaedge.in
~~~

Test the main hostname with the dedicated QuantaEdge API key:

~~~powershell
$publicBase = "https://ai-api.quantaedge.in/compat/v1"
Invoke-RestMethod "$publicBase/models" -Headers $headers
~~~

The Access-protected Harness hostname needs Authorization: Bearer plus CF-Access-Client-Id and CF-Access-Client-Secret headers.

## Troubleshooting

- DNS cannot resolve: check the published application route and DNS record.
- Tunnel down: check Docker Desktop, host networking, token volume provisioning and cloudflared logs.
- Cloudflare 502: verify FastAPI is running and cloudflared can reach 127.0.0.1:8000.
- Cloudflare 403 HTML: check the Access application and Service Auth policy.
- QuantaEdge 401/403 JSON: check the Bearer key and its scopes.
- Never resolve connectivity problems by binding FastAPI to 0.0.0.0 or publishing port 8000.

The tunnel token grants connector access. Rotate it in Cloudflare and re-run the secure token setup script if disclosed. Laptop sleep, shutdown or internet loss makes the API unavailable; production uptime requires an always-on host.
