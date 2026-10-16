# Local inference — text and voice (`sophia-inference`)

A language model served by the server's GPU, and a voice (recognition and synthesis) served by its CPU, routed by the model router like remote models: **same interface, switching is a model choice, no data leaves the cluster.** The namespace has **no network egress**: models are placed from the node, at pinned revisions and checksums.

## Choices

| Item | Choice | Reason |
|---|---|---|
| Text model | **Qwen3.5-9B**, GGUF **Q6_K** (7.5 GB, Apache 2.0) | **reliable tool calls** (MCP, skills, multi-agent): tau2-bench ≈ 87, against ≈ 36 for a similar-size model tried first; fits a 16 GB card with context |
| Server | llama.cpp (`llama-server`), pinned version | OpenAI-compatible API, tool calls (`--jinja`), parallel conversations, prompt cache |
| Context | 4 conversations × 32,000 tokens | hybrid model (8 full-attention layers out of 32): ≈ 32 KiB of cache per token |
| Internal reasoning | off by default (`--reasoning off`), can be re-enabled per request | measured: same tool reliability, loops twice as fast |
| Image | built in the cluster, CUDA compatible with the node's driver | the official image targeted a newer CUDA than the driver |
| GPU access | privileged container, driver library (`libcuda.so.1`) mounted from the host, **without** a `nvidia.com/gpu` resource | on this node the NVIDIA operator's container-toolkit hook fails; the device plugin is disabled |
| Speech recognition | **Parakeet TDT 0.6B v3** (ONNX int8), CPU | ≈ 5 % French error rate, 0.4 to 0.6 s per sentence |
| Speech synthesis | **Pocket TTS** (French model, int8), CPU | first sound in 75 ms, 4.6× faster than real time; the GPU stays with text |

## Measurements (entry-level 16 GB card, 2016 Xeon CPU)

| Measurement | Result |
|---|---|
| Tool calls (right tool, valid JSON arguments, result used) | 8/8 |
| One conversation | 16.4 tokens/s, first token 0.3 s |
| Four simultaneous conversations | 9.9 tokens/s each, 39 in total |
| Tool loop (search, weather, reminder), without reasoning | 4 to 21 s |

## The voice service (`sophia-voice`)

The code is not provided; its contract (OpenAI API, routed by the model router):

| Route | Role |
|---|---|
| `POST /v1/audio/transcriptions` | browser audio (webm/opus, mp4/aac, wav) → text |
| `POST /v1/audio/speech` | text → WAV; voices on an allow-list, unknown → default voice |
| `GET /v1/voices`, `GET /health` | available voices, status |

Rules: **numbers, times, dates and operations written out in words before synthesis** (the model cannot read digits); Markdown, links, emojis and tool notices removed; audio ≤ 10 MB and ≤ 120 s, text ≤ 2,000 characters; one job at a time per model. In the interface, the dictated sentence is sent, and the reply is read aloud sentence by sentence.

Voices: the model's catalogue, or a voice converted from a freely licensed recording (`export-voices.sh`, on the node, with the model's "cloning" variant). Never a person's voice without their consent.

## Files

| File | Content |
|---|---|
| `00-namespace-guardrails.yaml` | `PriorityClass`, `ResourceQuota`, `LimitRange` |
| `01-storage.yaml` | local model volume, mounted read-only |
| `02-build.yaml` | text server image |
| `03-llama-server.yaml` | text server (GPU) and Service |
| `04-network.yaml` | deny all, except the model router to both services |
| `05-voice.yaml` | voice service build and deployment (CPU) |
| `fetch-voice-models.sh`, `export-voices.sh` | models and voices, placed from the node |
| `bench.py` | benchmark: tool calls, single and four-way throughput — **against the server alone, never in production** |

## Procedure (administrator)

1. Text model placed on the node (`curl` at a pinned revision, `sha256sum -c`, SELinux label `container_file_t`); voice models: `fetch-voice-models.sh`.
2. Images: `oc start-build` for the text server and the voice service.
3. `00`, `01`, `04`, then `03` and `05`: `--dry-run=server`, then `apply`.
4. Model router: text and voice aliases, then add the aliases to restricted virtual keys.

**Limits:** 4 conversations at a time (a fifth waits); 32,000 tokens per conversation; voice from a small CPU model, correct but not very expressive.
