# Ask IQ local search service

The desktop runs Qwen3.5-0.8B Q4_0 from the llama.cpp maintainers' GGUF repository with llama.cpp on two CPU threads.
The service binds only `127.0.0.1:30002`; its OpenAI-compatible model name is
`hp-os-search-iq`. It starts at user login and remains ready
for explicit search requests. It uses no GPU, cloud account or API key.

The model download is 563,036,064 bytes, pinned to GGUF revision
`807dfd9a6fadbf703207aac3bfb0b2b3040d077c` and verified by SHA-256.
[Official base model and Apache-2.0 license](https://huggingface.co/Qwen/Qwen3.5-0.8B).
[Pinned GGUF](https://huggingface.co/ggml-org/Qwen3.5-0.8B-GGUF/tree/807dfd9a6fadbf703207aac3bfb0b2b3040d077c).

The service has a 2,048-token context, one request slot, two CPU threads,
a 200% CPU limit and a 2 GiB memory limit. Thinking is disabled in the server
chat template. Clients should also use `/no_think`, a JSON schema, and at most
96 output tokens for short query expansion. Search should retain the original
query and its filename/content results when this optional model is unavailable.
This small model suggests keywords; it does not establish file contents.

Run `python3 pkgs/hp-os-search-iq/verify.py` against a running service for two
bounded English/Chinese fixtures. The check reports actual latency and usage.
Service logs: `journalctl --user -u hp-os-search-iq`.

## Qualification

On Goran ARM64, llama.cpp 0.5.0 ran this model using two CPU threads, no GPU,
and the same 2 GiB cgroup limit. Two short requests completed in 0.66 and
0.35 seconds with 10 and 11 output tokens. Peak cgroup memory was 785 MiB.
These are short query measurements, not general model benchmarks.

The English hotel-invoice request preserved useful keywords. The Chinese
battery-life presentation request returned English battery/power keywords
and an overly broad sustainability suggestion. Original-query search remains
necessary. JSON format checks are not proof that an expansion preserves intent.

The earlier Qwen3-0.6B Q8_0 baseline used about 920 MiB and took 0.65–1.24
seconds for three requests with 31–39 output tokens. Prompts and output lengths
differed, so this is not a controlled speed comparison. The selected model is
newer and has a smaller download. NVIDIA-specific GPU runtimes are not needed
for this lightweight CPU task.
