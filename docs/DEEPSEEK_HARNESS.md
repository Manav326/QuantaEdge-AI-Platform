# DeepSeek Harness integration

DeepSeek Harness is a client of QuantaEdge AI Platform. It does not run a second model stack and does not bypass the QuantaEdge model gateway.

## Connection contract

Use the dedicated OpenAI-compatible surface:

| Harness location | Base URL |
|---|---|
| Docker Desktop container on the AI laptop | https://ai-api.quantaedge.in/compat/v1 |
| Native Windows Harness process on the AI laptop | http://127.0.0.1:8000/compat/v1 |
| Harness on another machine | https://ai-api.quantaedge.in/compat/v1 |

**For Docker Desktop, use the HTTPS Cloudflare Tunnel URL.** The Windows API intentionally listens only on 127.0.0.1:8000. A container's 127.0.0.1 is the container itself, and host.docker.internal:8000 cannot reach a service bound only to Windows loopback. Do not change the API to bind to 0.0.0.0, publish port 8000, or expose Ollama, PostgreSQL, or Redis to make this connection work.

The Docker path is:

~~~text
DeepSeek Harness container
  └─ HTTPS outbound request
       └─ Cloudflare Access service-auth policy
            └─ Cloudflare Tunnel connector on AI laptop
                 └─ http://localhost:8000
                      └─ QuantaEdge FastAPI /compat/v1
                           └─ existing Model Gateway → native Ollama
~~~

The API translates requests into the existing Model Gateway and Ollama provider. QuantaEdge web and Android clients continue using their existing /v1 routes.

## 1. Update the AI laptop and issue the API credential

After this change has been merged into main, update the local clone:

~~~powershell
cd D:\QuantaEdgeAI\projects\knowledge-engine
git pull origin main
~~~

Generate a separate, least-privilege API credential:

~~~powershell
.\scripts\enable-deepseek-harness.ps1
~~~

The script adds or reuses the deepseek-harness record in the existing local .env. A new 96-character hexadecimal key is displayed once. It has only chat and models:read scopes. Save it in the Harness custom provider settings or a password manager. To rotate it deliberately, run:

~~~powershell
.\scripts\enable-deepseek-harness.ps1 -Rotate
~~~

If a key was pasted into a chat, terminal transcript, issue, or other shared location, rotate it before connecting Harness. Restart the API after updating code or .env so the process reloads the credential registry:

~~~powershell
.\scripts\start-api.ps1
~~~

Do not put this credential in source code, a browser bundle, Android, Docker image layers, a project workspace mounted into the agent, or this repository.

## 2. Verify the Windows API locally

In a new PowerShell session, set the key without putting it in command history:

~~~powershell
$secureKey = Read-Host "DeepSeek Harness API key" -AsSecureString
$apiKey = [System.Net.NetworkCredential]::new("", $secureKey).Password
$headers = @{ Authorization = "Bearer $apiKey" }
$base = "http://127.0.0.1:8000/compat/v1"
~~~

Check model discovery:

~~~powershell
Invoke-RestMethod "$base/models" -Headers $headers
~~~

Send a non-streaming completion:

~~~powershell
$body = @{
    model = "qwen3.5-teacher-2b"
    messages = @(
        @{ role = "user"; content = "Explain evaporation in two sentences." }
    )
} | ConvertTo-Json -Depth 20

$response = Invoke-RestMethod "$base/chat/completions" -Method Post -Headers $headers -ContentType "application/json" -Body $body
$response.choices[0].message | ConvertTo-Json -Depth 10
~~~

The assistant text should be present in $response.choices[0].message.content.

## 3. Protect the Cloudflare route for Harness

The Cloudflare Tunnel connector must run on the AI laptop and forward ai-api.quantaedge.in to http://localhost:8000. Keep the API listener on 127.0.0.1:8000.

Use a dedicated Cloudflare Access service token for this Harness container in addition to the QuantaEdge API key:

1. In Cloudflare Zero Trust, open **Access → Service credentials → Service Tokens** and create a token named deepseek-harness-ai-laptop.
2. Open the existing self-hosted Access application for ai-api.quantaedge.in. Add a **Service Auth** policy that includes only this new service token. Preserve existing approved application-backend policies; do not replace them with a broad bypass or allow-all rule.
3. Keep the generated Client ID and Client Secret private. Do not paste either value into this repository, a chat, a Dockerfile, or the agent's workspace.

Cloudflare Access checks the service-token headers first. QuantaEdge then independently checks the Authorization: Bearer key and its scopes. This is intentional two-layer authentication.

## 4. Configure the Docker Harness container

### 4.1 Add the custom QuantaEdge provider

Open Harness **Settings → Models → Add model provider → Custom model API** and enter:

| Field | Value |
|---|---|
| Provider ID | quantaedge |
| Display name | QuantaEdge AI |
| Base URL | https://ai-api.quantaedge.in/compat/v1 |
| API protocol | OpenAI Chat Completions |
| API key | The rotated/dedicated deepseek-harness API key |

Add this model manually if model discovery is not offered or does not list it:

| Field | Value |
|---|---|
| Model ID | qwen3.5-teacher-2b |
| Display name | QuantaEdge Qwen 3.5 Teacher 2B |
| Context window | 4096 |
| Maximum output tokens | 700 |
| Input | Text |

Save the provider. Harness stores the API key in its managed credential store under $DSH_HOME; do not put it in Compose YAML or the workspace.

### 4.2 Add the Cloudflare Access headers to the Harness profile

Harness supports deployment-level provider headers in the profile's cordis.patch.yml. The default dsh web profile is web, so edit:

~~~text
$DSH_HOME/profiles/web/cordis.patch.yml
~~~

Add or merge the following provider entry. Replace both placeholders locally with the Cloudflare Service Token values; do not commit the real values:

~~~yaml
- id: llm-pi-ai
  config:
    providers:
      quantaedge:
        headers:
          CF-Access-Client-Id: "REPLACE_WITH_CLIENT_ID"
          CF-Access-Client-Secret: "REPLACE_WITH_CLIENT_SECRET"
~~~

If the file already has an llm-pi-ai entry, merge the providers.quantaedge.headers fields into that entry. Do not add a duplicate llm-pi-ai item or discard other configured providers/options. If Harness runs with a custom profile, use that profile's directory instead of web.

The profile lives in the persistent Harness home volume (the container's DSH_HOME, commonly /home/node/.dsh for Node-based images), **not** in the agent workspace. The two header values are stored as plain text in this file: protect the volume with host access controls and encrypted backups, and never mount it into the agent workspace. These headers are applied to model discovery and inference requests. Harness re-reads profile configuration on the next request, so a restart is not normally needed.

### 4.3 Keep the Harness web UI local

Publish the Harness UI only on the Docker host's loopback interface, for example 127.0.0.1:3080:3080 if that is the port used by your image. Do not expose the Harness web UI to the public internet or an untrusted LAN. The Harness agent can run tools and modify files, so mount only the workspace it is authorised to access; never mount the QuantaEdge repository's .env or the wider AI-laptop data folders into that workspace.

### 4.4 Verify from Harness itself

In Settings → Models, use **Fetch available models**. The provider should list:

~~~text
qwen3.5-teacher-2b
~~~

Select it and start a new session with a simple prompt. This end-to-end test verifies the container's outbound HTTPS path, Cloudflare service-token policy, QuantaEdge bearer authentication, model discovery, and inference.

Do not use http://127.0.0.1:8000 or http://host.docker.internal:8000 as the Docker provider URL with the current loopback-only API binding. Do not publish the QuantaEdge API port to the host network as a workaround.

## Supported request surface

The compatibility layer provides:

- OpenAI-style GET /models discovery.
- OpenAI Chat Completions request and response envelopes.
- Bearer authentication, using the same scoped API-key registry as X-API-Key.
- Server-sent event streaming, including the terminal [DONE] marker and optional usage chunks.
- System, developer, user, assistant and tool message roles.
- Function tool definitions, assistant tool-call responses and tool-result history.
- Temperature, top-p, output-token limits, stop sequences, seed and JSON response modes.

It deliberately remains text-only for the currently configured model profile. Image input, OpenAI Responses, Anthropic Messages, audio and embeddings are not exposed through this Harness provider.

Tool-call transport is implemented, but reliable tool selection and execution depend on the installed model. The current 2B profile is a development candidate and must pass real local tool-use tests before relying on computer-use or coding agents.

## Troubleshooting

- Cloudflare 403 HTML or an Access block page: check that the Harness profile has the correct Client ID and Client Secret headers and that the named service token is included in the Access Service Auth policy.
- QuantaEdge 401: check the dedicated Harness API key and restart the API after changing .env.
- QuantaEdge 403 JSON: check that the key has the required chat or models:read scope.
- Model absent: use the logical profile ID qwen3.5-teacher-2b, not qwen3.5:2b-q4_K_M.
- 503: confirm Ollama is running, the model is installed, and /ready reports the required services healthy.
- Model discovery fails: verify the base URL is exactly https://ai-api.quantaedge.in/compat/v1, the Cloudflare tunnel targets http://localhost:8000, and the Access headers are applied to the quantaedge provider.
- Streaming appears buffered: verify the proxy does not buffer text/event-stream; the API emits Cache-Control: no-cache and X-Accel-Buffering: no.
- Tool calls are absent or malformed: test the installed model's tool-use ability directly before enabling agent tools in a production workflow.

This document describes the API integration. It does not claim that the Cloudflare Access policy, service token, tunnel, or Harness UI have been deployed and runtime-verified. Complete the checks in section 4.4 before treating the integration as connected.
