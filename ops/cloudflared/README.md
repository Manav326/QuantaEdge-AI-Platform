# Cloudflare Tunnel in Docker Desktop (Windows AI laptop)

This repository runs cloudflared as a Docker Desktop container. FastAPI remains a native Windows process listening only on 127.0.0.1:8000. Docker Desktop host networking lets the cloudflared container reach the Windows host's loopback address without widening the API listener or publishing port 8000.

## Prerequisites

- The quantaedge.in zone is active in the Cloudflare account.
- QuantaEdge FastAPI is running at http://127.0.0.1:8000.
- Docker Desktop uses Linux containers and is version 4.34 or later.
- Docker Desktop host networking is enabled in Settings → Resources → Network → Enable host networking. Apply the change and restart Docker Desktop.
- Enhanced Container Isolation is disabled. Docker Desktop host networking is incompatible with it.
- Docker Desktop is signed in where required by the installed version.

Host networking shares the host network namespace with the cloudflared container. The connector can consequently reach other services bound to host loopback, not only FastAPI. The optional connector is defined in docker-compose.cloudflare.yml, drops all Linux capabilities, uses no-new-privileges and a read-only root filesystem. Do not run untrusted containers with host networking.

## 1. Create a remotely managed tunnel

Cloudflare recommends remotely managed tunnels for Docker deployments.

1. Open the Cloudflare dashboard and select the quantaedge.in account.
2. Go to Networking → Tunnels and select Create Tunnel.
3. Choose Cloudflared, name it quantaedge-ai-docker, and create it.
4. On the connector installation screen, select Docker and copy the tunnel token. Treat it as a password. Do not paste it into Git, chat, an image build, or a command line.
5. In the tunnel's Published application routes, add these hostnames. Both routes point to the same local API, but have distinct access policies.

| Hostname | Service URL | Purpose |
|---|---|---|
| ai-api.quantaedge.in | http://127.0.0.1:8000 | QuantaEdge backend and other approved server-side clients |
| harness-ai-api.quantaedge.in | http://127.0.0.1:8000 | Dedicated Harness endpoint protected by Cloudflare Access |

The dashboard creates the required DNS records for the tunnel. Keep FastAPI's listener at 127.0.0.1:8000. Because cloudflared uses Docker host networking, 127.0.0.1:8000 is the Windows host's loopback listener.

Do not create routes to Ollama (11434), PostgreSQL (5432), Redis (6379), Docker's API, or the Harness web UI.

## 2. Store the tunnel token outside the repository

From PowerShell in the repository:

~~~powershell
.\scripts\set-cloudflare-tunnel-token.ps1
~~~

The script prompts for the tunnel token as a secure input and writes it to:

~~~text
D:\QuantaEdgeAI\secrets\cloudflare-tunnel.token
~~~

It restricts the folder ACL to the current Windows user, SYSTEM and local Administrators. This file is mounted read-only as a Compose secret only into cloudflared. It is outside the Git repository and is not part of the Harness workspace.

## 3. Enable and start the Docker connector

Confirm Docker Desktop host networking is enabled and Docker Desktop has restarted. Then run:

~~~powershell
.\scripts\start-cloudflared.ps1
~~~

This starts only the cloudflared service using the additional docker-compose.cloudflare.yml file. It does not restart PostgreSQL, Redis, the Windows API or Ollama. Keeping the connector in a separate Compose file means ordinary infrastructure startup does not require the tunnel-token file.

Check the container:

~~~powershell
docker compose -f docker-compose.yml -f docker-compose.cloudflare.yml ps cloudflared
docker compose -f docker-compose.yml -f docker-compose.cloudflare.yml logs --tail 60 cloudflared
~~~

In Cloudflare → Networking → Tunnels, the connector should show Healthy/Connected. The container has no published inbound ports; it establishes outbound connections to Cloudflare.

To stop the connector:

~~~powershell
docker compose -f docker-compose.yml -f docker-compose.cloudflare.yml stop cloudflared
~~~

To start it again:

~~~powershell
docker compose -f docker-compose.yml -f docker-compose.cloudflare.yml start cloudflared
~~~

## 4. Protect the Harness hostname separately

Do not put the Harness-only Access policy on ai-api.quantaedge.in unless every existing API caller has also been provisioned with a Cloudflare Access service token. That would otherwise block existing backend clients that currently authenticate using only their QuantaEdge API key.

Instead:

1. In Cloudflare Zero Trust, create a Service Token named deepseek-harness-ai-laptop.
2. Create a Self-hosted Access application for harness-ai-api.quantaedge.in only.
3. Add a Service Auth policy that includes this token. Do not use Bypass or Allow Everyone.
4. Preserve the separate ai-api.quantaedge.in route and its existing approved server-to-server authentication.
5. Store the Client ID and Client Secret in the private Harness profile configuration as described in docs/DEEPSEEK_HARNESS.md.

Requests to the Harness hostname must pass both Cloudflare Access service-token authentication and QuantaEdge Bearer API-key authentication.

## 5. Verify the tunnel

After the dashboard shows the connector as Healthy, run:

~~~powershell
Resolve-DnsName ai-api.quantaedge.in
Resolve-DnsName harness-ai-api.quantaedge.in
~~~

Test the main API hostname with the dedicated QuantaEdge API key:

~~~powershell
$publicBase = "https://ai-api.quantaedge.in/compat/v1"
Invoke-RestMethod "$publicBase/models" -Headers $headers
~~~

The Access-protected Harness hostname needs both authentication layers:

~~~powershell
$accessHeaders = @{
    Authorization = "Bearer $apiKey"
    "CF-Access-Client-Id" = $clientId
    "CF-Access-Client-Secret" = $clientSecret
}
$harnessBase = "https://harness-ai-api.quantaedge.in/compat/v1"
Invoke-RestMethod "$harnessBase/models" -Headers $accessHeaders
~~~

Do not print or paste the key or either Access value into shared logs or chat.

## Troubleshooting

- DNS name cannot be resolved: check that the published application route was saved and its DNS record exists.
- Tunnel shows down or inactive: check Docker Desktop is running, host networking is enabled, the token file exists, and cloudflared logs.
- Cloudflare 502: verify the API is running and the cloudflared container can access http://127.0.0.1:8000 using host networking.
- Cloudflare 403 HTML: check the Access application hostname, Service Auth policy, and both CF-Access headers.
- QuantaEdge 401 JSON: check the dedicated Bearer API key and API process restart after .env changes.
- QuantaEdge 403 JSON: check the service key has the required chat or models:read scope.
- Do not resolve connectivity problems by changing FastAPI to 0.0.0.0 or publishing port 8000.

The tunnel token is a credential that can run a connector for this tunnel. Rotate it in Cloudflare and replace the local token file if it is disclosed. Laptop sleep, shutdown or internet loss makes the API unavailable; production uptime requires an always-on host.