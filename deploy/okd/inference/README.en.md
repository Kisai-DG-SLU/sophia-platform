# Local inference — text, vision, voice and images (`sophia-inference`)

A language model that also reads images, served by the server's GPU, a voice (recognition and synthesis) and an image generator served by its CPU, routed by the model router like remote models: **same interface, switching is a model choice, no data leaves the cluster.** The namespace has **no network egress**: models are placed from the node, at pinned revisions and checksums.

## Choices

| Item | Choice | Reason |
|---|---|---|
| Text model | **Qwen3.6-35B-A3B**, GGUF **UD-Q4_K_M** (22.66 GB, Apache 2.0), **hybrid**: experts of the first 34 layers in RAM (`--n-cpu-moe 34`), the rest and the cache on the card | better quality on the services' series (80/85, against 74/85 for Qwen3.5-9B under the same conditions); mixture-of-experts model (≈ 3 billion active parameters per token), so partly readable by the CPU: 13.06 GB of card memory at the median, out of 16 |
| Hybrid model settings | 4,096-token prompt batches (`-b`/`-ub`); op offload threshold at 128 tokens (`GGML_OP_OFFLOAD_MIN_BATCH`) | a single upload of the experts per batch: cold reading divided by 3.2; a short prompt stays on the CPU, without copying the experts: 0.93 s at the median instead of 1.86 s |
| Text server CPU | **20 exclusive CPUs**, 20 threads: `Guaranteed` pod (requests equal to limits, wait container included), kubelet with the `static` CPU policy | the experts in RAM are computed by the CPU: reserved cores compete neither with etcd and the API nor with the voice; 20 CPUs, one socket of the reference node |
| Server | llama.cpp (`llama-server`), pinned version | OpenAI-compatible API, tool calls (`--jinja`), parallel conversations, prompt cache |
| Context | 8-bit shared cache: 245,760 tokens, 61,440 per conversation | 8 slots guaranteed 30,720 tokens each; beyond 61,440, re-reading a conversation takes more than two minutes |
| Vision | the same model's `mmproj` module (F16, 0.9 GB) on the GPU (`--mmproj`), at most 2,048 tokens per image | read homework, a photo, a document without leaving the server; the cap bounds memory and time |
| Internal reasoning | off by default (`--reasoning off`), can be re-enabled per request | measured: same tool reliability, loops twice as fast |
| Image | built in the cluster, CUDA compatible with the node's driver | the official image targeted a newer CUDA than the driver |
| GPU access | privileged container, driver library (`libcuda.so.1`) mounted from the host, **without** a `nvidia.com/gpu` resource | on this node the NVIDIA operator's container-toolkit hook fails; the device plugin is disabled |
| Speech recognition | **Parakeet TDT 0.6B v3** (ONNX int8), CPU | ≈ 5 % French error rate, 0.4 to 0.6 s per sentence |
| Speech synthesis | Kyutai's **Pocket TTS** (French model, weights without cloning, in float32), CPU, 2 threads | first sound in 75 ms, 4.6× faster than real time in int8; the GPU stays with text. Under the 4-CPU limit, 120 characters in 1.4 to 1.5 s with 2 threads, against 1.7 to 1.8 s with 4 (int8). float32, chosen by ear (fewer swallowed words), is about 1.5 times slower |
| Image generation | **stable-diffusion.cpp**, 1-step SDXL-Turbo + TAESDXL decoder, CPU, 512 × 512 | about ten seconds per image without a GPU; the card stays with text. **SDXL-Turbo licence: non-commercial use** — replace it with an openly licensed model for commercial use |
| Image check | image classifier (Apache 2.0) after each generation | a deterministic check around the model's output, on top of the rules applied before |

## Measurements (entry-level 16 GB card, 2016 Xeon CPU, 20 reserved CPUs)

| Measurement | Result |
|---|---|
| Services' quality series (answers judged by the services' code) | 80/85 (74/85 for Qwen3.5-9B) |
| One conversation | ≈ 27 tokens/s |
| Six simultaneous requests | 5.4 to 6.4 tokens/s each (minimum, median) |
| First token of a turn already cached, with six requests | 7.8 s at worst (3.45 s for Qwen3.5-9B) |
| Cold reading of a prompt | 8,000 tokens in 14.7 s; 32,000 in 61 s; 61,000 in 127 s |
| GPU memory (NVML) | 13.06 GB at the median, 13.69 at most, out of 16.10 |

The first word can therefore take 6 to 13 s when several people write at the same time: that is the price of quality, accepted for the reference installation. The previous model, **Qwen3.5-9B** Q6_K (7.5 GB, fully on the card, 16.4 tokens/s alone), stays on the volume for rollback.

## Model volume (node prerequisite)

Models live on a dedicated logical volume, created once on the node following [`../../stockage-persistant.en.md`](../../stockage-persistant.en.md) — `LV_NAME=lv-models`, `LV_SIZE=200G`, `MOUNT_POINT=${MODELS_MOUNT_POINT}` (for instance `/var/mnt/models`), XFS, persistent mount —, then exposed by `01-storage.yaml` (local `Retain` PV, bound by name to `pvc-models`, mounted read-only). 200 GB from the start: a local volume cannot grow, and it holds text, vision, voice, image models and the tools' data (`${MODELS_MOUNT_POINT}/skills`, see [`../skills/`](../skills/)).

```bash
sudo lvs ${VG_NAME}                       # lv-models present
df -h ${MODELS_MOUNT_POINT}               # mounted, XFS
ls -lZ ${MODELS_MOUNT_POINT}              # container_file_t label
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
| `POST /v1/audio/speech` | text → WAV or PCM; voices on an allow-list, unknown → default voice. With `"stream_format": "audio"` and `"response_format": "pcm"`, 16-bit PCM arrives **as it is decoded**, with an `X-Sample-Rate` header; a WAV stream is refused (400), since its size is only known at the end; without `stream_format`, nothing changes |
| `GET /v1/voices`, `GET /health` | available voices, status |

Rules: **numbers, times, dates and operations written out in words before synthesis** (the model cannot read digits; in French, "+" is written "plusse" so that the final "s" is pronounced); Markdown, links, emojis and tool notices removed; audio ≤ 10 MB and ≤ 120 s, text ≤ 2,000 characters.

Synthesis (in service):

- **a single engine, served in order of arrival**: at most 8 syntheses waiting (`TTS_MAX_WAITING`), beyond that a 503; the engine is not thread-safe, and a second one would add no compute within the pod's CPU limit;
- **relayed stop**: if the client drops the connection (playback stopped), generation stops and the slot is released (about 20 ms measured);
- **duration guard**: beyond max(1.8 s; 0.135 s × characters), or if the model does not signal the end of its generation, synthesis is stopped: 502 without streaming, early end with streaming;
- **two compute threads** (`TTS_THREADS=2`): generation and decoding each get that many, i.e. the pod's 4-CPU limit; with 4, they competed for 8 threads;
- **float32** (`TTS_INT8=0`): fewer swallowed words than int8, for computation about 1.5 times longer;
- **paired root** (`VOICE_MODELS`, `TTS_CONFIG`): one folder per weights revision, with the voices computed by its twin weights and its configuration; changing revision means changing folder, and rolling back removes these two variables.

In the interface, the reply is read **while it is being written**: in groups of sentences (the first from about forty characters, then 80 to 150), chained without gaps, with a timeout that accounts for the queue; a late group is retried or merged into the next one, and is only skipped on a service error, never silently. In service, verified on a long reply (the voice starts before the text ends). Not done yet: the chat requests each group in one block and does not consume streamed PCM yet; relaying the stream through the model router remains to be proven on the real path (without relaying, the PCM arrives whole, as before).

Voices: the model's catalogue, or a household voice derived from a short sample (`export-voices.sh`, on the node, with the model's "cloning" variant, in a throwaway container; the sample goes into no repository and is deleted from the node after the computation; only the voice embedding remains, next to the others). **Never a person's voice without their consent**; the reference installation's default voice is that of a consenting member of the family.

**A voice embedding is tied to the weights revision that computed it.** The weights without cloning exist in several revisions, with different weights, and the same voice does not have the same embedding from one revision to another. A voice computed with the "cloning" weights of a Pocket TTS version must be read by the **twin weights without cloning** of the same version, not by another revision: otherwise it becomes unintelligible (noise), while the computation's test sentence is perfect. Weights, tokenizer, catalogue voices and household voices of one revision therefore live under **one root** (`VOICE_MODELS`, `TTS_CONFIG`); the former root stays in place for rollback.

**Listening bench before any voice goes live**, on the node, **under the service's conditions** (same weights, same version, offline, models read-only), in int8 and in float32, with a catalogue voice as a control: a test sentence produced by other weights proves nothing. The bench ruled out two false leads (sample length, int8) before finding the revision.

Credit: Pocket TTS, by **Kyutai**; weights under **CC BY 4.0**, code under MIT. Cloning is forbidden without the person's explicit consent.

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
   Node kubelet with the `static` CPU policy (`KubeletConfig` of the node's pool, `cpuManagerPolicy: static`): without it, the pod stays `Guaranteed` but its 20 CPUs are not reserved. Changing the policy reboots the node. Also check capacity: the node's CPU requests, plus 20, must fit in the allocatable CPU.
1. Text model and vision module placed on the node in `qwen3.6-35b-a3b/` (`curl` at a pinned revision, `sha256sum -c`, SELinux label `container_file_t`): `Qwen3.6-35B-A3B-UD-Q4_K_M.gguf` from the `unsloth/Qwen3.6-35B-A3B-MTP-GGUF` repository, saved as `Qwen3.6-35B-A3B-UD-Q4_K_M-MTP.gguf` (it also carries the multi-token prediction head, unused here), and `mmproj-F16.gguf` from the `unsloth/Qwen3.6-35B-A3B-GGUF` repository; voice models: `fetch-voice-models.sh`; image models: `fetch-image-models.sh`.
2. Images: `oc start-build` for the text server, the voice service, the image generator and its classifier.
3. `00`, `01`, `04`, then `03`, `05` and `06`: `--dry-run=server`, then `apply`. Variables, through a named substitution: `01-storage.yaml` carries `${NODE_NAME}`, the node carrying the volume (`oc get nodes`), and `${MODELS_MOUNT_POINT}`, the models volume's mount point (`envsubst '${NODE_NAME} ${MODELS_MOUNT_POINT}' < 01-storage.yaml | oc apply -f -`); `03-llama-server.yaml` carries `${NVIDIA_LIB_DIR}`, the node directory holding `libcuda.so.1`, the same as for the node exporter (`envsubst '${NVIDIA_LIB_DIR}' < 03-llama-server.yaml | oc apply -f -`); `05-voice.yaml` carries `${VOICE_REVISION}`, the folder of `voice/` that groups one revision of the no-cloning weights, the voices computed with its twin weights and its configuration (`envsubst '${VOICE_REVISION}' < 05-voice.yaml | oc apply -f -`).
4. Model router: text and voice aliases, then add the aliases to restricted virtual keys.

**Limits:** 8 conversations at a time (a ninth waits), each guaranteed 30,720 tokens; up to 61,440 tokens per conversation when the others are shorter, beyond that the conversation is summarised (oldest exchanges) and an oversized file is refused with a clear message; voice from a small CPU model, correct but not very expressive.
