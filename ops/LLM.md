# Local interpretation operations

Deployed model: `qwen3:1.7b` (Ollama model digest prefix `8f68893c685c`, Q4_K_M, Apache 2.0). Runtime: Ollama 0.35.0, CPU. Weights are outside the website under the Ollama service account’s model store. No API key or cloud inference is used.

## Services and configuration

- Install Ollama from its official Linux distribution, then `ollama pull qwen3:1.7b`. Model artifacts are verified by Ollama during pull.
- `ops/ollama-handspeak.conf` is the service drop-in at `/etc/systemd/system/ollama.service.d/handspeak.conf`: loopback-only 127.0.0.1:11434, cloud features disabled, one loaded model, one parallel inference, 2048-token context, 4 GiB memory cap, 220% CPU quota. Inference requests use two threads.
- Website systemd environment: `HANDSPEAK_LLM_ENABLED=1` and `HANDSPEAK_LLM_MODEL=qwen3:1.7b`. Backend always connects to the fixed loopback address and bypasses proxy environment variables; clients cannot supply a model, URL, tools, or system prompt.
- Check `systemctl status ollama`, `ollama list`, `ollama ps`, and `/api/interpret/status`. Model presence does not mean it is already loaded into memory.
- Disable via `HANDSPEAK_LLM_ENABLED=0` and restart handspeak; camera, editing, accounts, and history continue to work.

## Boundaries

`POST /api/interpret` takes `{"text":"I WANT WATER PLEASE"}`. Up to 500 characters, 3 attempts/client-IP/minute, one in-flight request per website process, 45-second upstream timeout. Busy/unavailable/malformed outputs return 503; client throttling returns 429. Cross-origin POST protections match the rest of the application. Limits are process-local and reset on restart. Shared-network users share the IP quota.

Only text is sent on an explicit click. No image, history, face data, identity, or account record enters the model request. Drafts/results are not persisted by this endpoint. Debug logging is disabled; never enable prompt logging on a public installation without revisiting the privacy notice. User-selected Save persists the current message under existing history rules.

The model uses constrained JSON, deterministic temperature, no tools, no conversation memory, and no thinking output. Prompt instructions request minimal English editing and clarification rather than invented details. Negation, numbers, and dropped question marks have conservative lexical checks; these do not establish semantic correctness. Users must compare original and suggestion. Application tests mock failures; real-model probes cover a few examples only, not ASL accuracy.

Observed development timings: initial model load/request about 21 seconds; warm short drafts about 3–5 seconds, with some longer prompt-processing requests. CPU contention and longer drafts can increase this. One early ambiguity probe was echoed unhelpfully; the prompt was revised and additional ambiguous examples requested clarification. Do not claim reliable ASL-to-English interpretation from these checks.

References: [Ollama Linux installation](https://docs.ollama.com/linux), [generate API and structured format](https://docs.ollama.com/api/generate), [model and license](https://ollama.com/library/qwen3:1.7b).
