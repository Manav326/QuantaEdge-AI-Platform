# DeepSeek Harness integration

DeepSeek Harness is a client of QuantaEdge AI Platform. It does not run a second model stack and does not bypass the QuantaEdge model gateway.

## Connection contract

Use the dedicated OpenAI-compatible surface:

- Base URL: `https://ai-api.quantaedge.in/compat/v1` when using the configured Cloudflare Tunnel.
- Local Base URL: `http://127.0.0.1:8000/compat/v1` when Harness runs on the AI laptop.
- Protocol: OpenAI Chat Completions.
- Credential: the dedicated `deepseek-harness` API key.
- Model ID: `qwen3.5-teacher-2b` (the logical QuantaEdge profile, not the raw Ollama tag).

The API translates requests into the existing Model Gateway and Ollama provider. The QuantaEdge web and Android clients continue using their existing `/v1` routes.

## 1. Update the AI laptop

After this change has been merged into `main`, update the local clone:

```powershell
cd D:\QuantaEdgeAI\projects\knowledge-engine
git pull origin main
```

Generate a separate, least-privilege API credential:

```powershell
.\scripts\enable-deepseek-harness.ps1
```

The script adds or reuses the `deepseek-harness` record in the existing local `.env`. A new 96-character hexadecimal key is displayed once. Save it in the Harness provider settings or a password manager. It has only `chat` and `models:read` scopes. To rotate it deliberately, run:

```powershell
.\scripts\enable-deepseek-harness.ps1 -Rotate
```

Restart the API after updating code or `.env`:

```powershell
.\scripts\start-api.ps1
```

Do not copy the credential into source code, a browser bundle, Android, this repository, or a shared terminal transcript.

## 2. Verify the API locally

In a new PowerShell session, set the key without putting it in command history:

```powershell
$secureKey = Read-Host "DeepSeek Harness API key" -AsSecureString
$apiKey = [System.Net.NetworkCredential]::new("", $secureKey).Password
$headers = @{ Authorization = "Bearer $apiKey" }
$base = "http://127.0.0.1:8000/compat/v1"
```

Check model discovery:

```powershell
Invoke-RestMethod "$base/models" -Headers $headers
```

Send a non-streaming completion:

```powershell
$body = @{
    model = "qwen3.5-teacher-2b"
    messages = @(
        @{ role = "user"; content = "Explain evaporation in two sentences." }
    )
} | ConvertTo-Json -Depth 20

Invoke-RestMethod "$base/chat/completions" -Method Post -Headers $headers -ContentType "application/json" -Body $body
```

Check streaming from PowerShell using `curl.exe` (not the PowerShell `curl` alias):

```powershell
$streamBody = '{"model":"qwen3.5-teacher-2b","stream":true,"messages":[{"role":"user","content":"Count from one to five."}]}'
curl.exe -N "$base/chat/completions" -H "Authorization: Bearer $apiKey" -H "Content-Type: application/json" -d $streamBody
```

The streaming response should contain `chat.completion.chunk` events and end with `data: [DONE]`.

## 3. Configure DeepSeek Harness

In Harness, open **Settings → Models → Add model provider → Custom model API** and enter:

| Field | Value |
|---|---|
| Provider ID | `quantaedge` |
| Display name | `QuantaEdge AI` |
| Base URL | `https://ai-api.quantaedge.in/compat/v1` |
| API protocol | `OpenAI Chat Completions` |
| API key | The dedicated `deepseek-harness` key |

For a local Harness process on the AI laptop, use `http://127.0.0.1:8000/compat/v1` instead of the public URL.

Add this model manually if model discovery is not offered or returns no models:

| Field | Value |
|---|---|
| Model ID | `qwen3.5-teacher-2b` |
| Display name | `QuantaEdge Qwen 3.5 Teacher 2B` |
| Context window | `4096` |
| Maximum output tokens | `700` |
| Input | Text |

Save the provider and select the model for a new session. The API's model listing is available at `GET /compat/v1/models`, so Fetch available models should also work.

## 4. Public access boundary

The public URL works only when Cloudflare Tunnel on the AI laptop forwards `ai-api.quantaedge.in` to the FastAPI listener at `http://localhost:8000`. Keep Ollama `11434`, PostgreSQL `5432`, and Redis `6379` private. Do not expose the Ollama endpoint directly.

If Harness runs on a different machine or server, use the public HTTPS URL. Do not use `127.0.0.1` from a remote Harness host; that address would refer to the Harness machine itself.

## Supported request surface

The compatibility layer provides:

- OpenAI-style `GET /models` discovery.
- OpenAI Chat Completions request and response envelopes.
- Bearer authentication, using the same scoped API-key registry as `X-API-Key`.
- Server-sent event streaming, including the terminal `[DONE]` marker and optional usage chunks.
- System, developer, user, assistant and tool message roles.
- Function tool definitions, assistant tool-call responses and tool-result history.
- Temperature, top-p, output-token limits, stop sequences, seed and JSON response modes.

It deliberately remains text-only for the currently configured model profile. Image input, OpenAI Responses, Anthropic Messages, audio and embeddings are not exposed through this Harness provider.

Tool-call transport is implemented, but reliable tool selection and execution depend on the installed model. The current 2B profile is a development candidate and must pass real local tool-use tests before relying on computer-use or coding agents.

## Troubleshooting

- `401`: check that the dedicated Harness key is correct and that the API was restarted after changing `.env`.
- `403`: the key must have `chat` and/or `models:read` as appropriate.
- Model absent: use the logical profile ID `qwen3.5-teacher-2b`, not `qwen3.5:2b-q4_K_M`.
- `503`: confirm Ollama is running, the model is installed, and `/ready` reports the required services healthy.
- Model discovery fails remotely: test `GET /compat/v1/models` with the same Bearer key and confirm Cloudflare Tunnel forwards to port 8000.
- Streaming appears buffered: verify the proxy does not buffer `text/event-stream`; the API emits `Cache-Control: no-cache` and `X-Accel-Buffering: no`.
- Tool calls are absent or malformed: test the installed model's tool-use ability directly before enabling agent tools in a production workflow.

This document describes the API integration. It does not confirm that the AI laptop, tunnel, or Harness UI has been deployed and connected; those are runtime verification steps.
