# Local inference — text, vision, voice and images (`sophia-inference`)

A language model that also reads images, served by the server's GPU, a voice (recognition and synthesis) and an image generator served by its CPU, routed by the model router like remote models: **same interface, switching is a model choice, no data leaves the cluster.** The namespace has **no network egress**: models are placed from the node, at pinned revisions and checksums.

## Choices

| Item | Choice | Reason |
|---|---|---|
| Text model | **Qwen3.5-9B**, GGUF **Q6_K** (7.5 GB, Apache 2.0) | **reliable tool calls** (MCP, skills, multi-agent): tau2-bench ≈ 87, against ≈ 36 for a similar-size model tried first; fits a 16 GB card with context |
| Server | llama.cpp (`llama-server`), pinned version | OpenAI-compatible API, tool calls (`--jinja`), parallel conversations, prompt cache |
| Context | 8-bit shared cache: 245,760 tokens, 61,440 per conversation | hybrid model (8 full-attention layers out of 32): ≈ 17 KiB of cache per token in 8 bits; same memory as 131,072 tokens in 16 bits |
| Vision | the same model's `mmproj` module (F16, 0.9 GB) on the GPU (`--mmproj`), at most 2,048 tokens per image | read homework, a photo, a document without leaving the server; the cap bounds memory and time |
| Internal reasoning | off by default (`--reasoning off`), can be re-enabled per request | measured: same tool reliability, loops twice as fast |
| Image | built in the cluster, CUDA compatible with the node's driver | the official image targeted a newer CUDA than the driver |
| GPU access | privileged container, driver library (`libcuda.so.1`) mounted from the host, **without** a `nvidia.com/gpu` resource | on this node the NVIDIA operator's container-toolkit hook fails; the device plugin is disabled |
| Speech recognition | **Parakeet TDT 0.6B v3** (ONNX int8), CPU | ≈ 5 % French error rate, 0.4 to 0.6 s per sentence |
| Speech synthesis | **Pocket TTS** (French model, int8), CPU | first sound in 75 ms, 4.6× faster than real time; the GPU stays with text |
| Image generation | **stable-diffusion.cpp**, 1-step SDXL-Turbo + TAESDXL decoder, CPU, 512 × 512 | about ten seconds per image without a GPU; the card stays with text. **SDXL-Turbo licence: non-commercial use** — replace it with an openly licensed model for commercial use |
| Image check | image classifier (Apache 2.0) after each generation | a deterministic check around the model's output, on top of the rules applied before |

## Measurements (entry-level 16 GB card, 2016 Xeon CPU)

| Measurement | Result |
|---|---|
| Tool calls (right tool, valid JSON arguments, result used) | 8/8 |
| One conversation | 16.4 tokens/s, first token 0.3 s |
| Four simultaneous conversations | 9.9 tokens/s each, 39 in total |
| Tool loop (search, weather, reminder), without reasoning | 4 to 21 s |
| Fact hidden in ≈ 97,000 tokens | found (at 15 % and 60 %) |
| Reading a very long prompt | ≈ 420 tokens/s (97,000 tokens ≈ 4 min) |

## Model volume (node prerequisite)

Models live on a dedicated logical volume, created once on the node following [`../../stockage-persistant.en.md`](../../stockage-persistant.en.md) — `LV_NAME=lv-models`, `LV_SIZE=200G`, `MOUNT_POINT=/var/mnt/models`, XFS, persistent mount —, then exposed by `01-storage.yaml` (local `Retain` PV, bound by name to `pvc-models`, mounted read-only). 200 GB from the start: a local volume cannot grow, and it holds text, vision, voice, image models and the tools' data (`/var/mnt/models/skills`, see [`../skills/`](../skills/)).

```bash
sudo lvs ${VG_NAME}                       # lv-models present
df -h /var/mnt/models                     # mounted, XFS
ls -lZ /var/mnt/models                    # container_file_t label
```

## Vision

The vision module (`mmproj-F16.gguf`) comes from the same repository and revision as the model, placed from the node with its checksum, then loaded with `--mmproj`. The interface scales photos down to 2,048 px on their longest side before sending; the model router declares the alias `supports_vision`. Fallback if GPU memory runs out: `--no-mmproj-offload` (vision on CPU, slower).

## Image generation (`sophia-image-gen`)

Two containers in one `sophia-inference` pod, without network egress:

| Container | Role | Port |
|---|---|---|
| `sd-server` | stable-diffusion.cpp (MIT): SDXL-Turbo + TAESDXL, quantised to `q8_0`, `/sdapi/v1/txt2img` API | 1234 |
| `nsfw` | classifier for generated images (`POST /classer` → probability), single compute thread | 8001 |

Only the `image` MCP server in `sophia-skills` can reach this pod ([`../skills/`](../skills/), protection rules): neither the interface nor the model router. The code of both images is not provided; their contract is above. Models: `fetch-image-models.sh`, from the node (≈ 7.3 GB, pinned revisions and SHA-256).

## The voice service (`sophia-voice`)

The code is not provided; its contract (OpenAI API, routed by the model router):

| Route | Role |
|---|---|
| `POST /v1/audio/transcriptions` | browser audio (webm/opus, mp4/aac, wav) → text |
| `POST /v1/audio/speech` | text → WAV; voices on an allow-list, unknown → default voice |
| `GET /v1/voices`, `GET /health` | available voices, status |

Rules: **numbers, times, dates and operations written out in words before synthesis** (the model cannot read digits; in French, "+" is written "plusse" so that the final "s" is pronounced); Markdown, links, emojis and tool notices removed; audio ≤ 10 MB and ≤ 120 s, text ≤ 2,000 characters; one job at a time per model. In the interface, the dictated sentence is sent, and the reply is read aloud sentence by sentence.

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
| `06-image.yaml` | builds, deployment, Service and network ingress of the image generator and its classifier (CPU) |
| `fetch-voice-models.sh`, `export-voices.sh` | models and voices, placed from the node |
| `fetch-image-models.sh` | image models and classifier, placed from the node |
| `bench.py` | benchmark: tool calls, single and four-way throughput — **against the server alone, never in production** |

## Procedure (administrator)

0. `lv-models` volume created and mounted on the node (above).
1. Text model and vision module placed on the node (`curl` at a pinned revision, `sha256sum -c`, SELinux label `container_file_t`); voice models: `fetch-voice-models.sh`; image models: `fetch-image-models.sh`.
2. Images: `oc start-build` for the text server, the voice service, the image generator and its classifier.
3. `00`, `01`, `04`, then `03`, `05` and `06`: `--dry-run=server`, then `apply`.
4. Model router: text and voice aliases, then add the aliases to restricted virtual keys.

**Limits:** 4 conversations at a time (a fifth waits); 61,440 tokens per conversation, beyond that the conversation is summarised (oldest exchanges) and an oversized file is refused with a clear message; voice from a small CPU model, correct but not very expressive.
