# Local LLM release — October 2, 2026 (Asia/Manila)

Live at https://handspeak.cvsu.dev. Local Ollama 0.35.0 / Qwen3 1.7B provides explicit, user-reviewed draft interpretation. No API key or cloud LLM is used. Camera frames remain on-device; clicking Interpret sends only the draft text to this server.

## Verified

- 70 regression tests passed. Gateway checks include validation, busy/rate limits, malformed/truncated output, timeout capacity release, and conservative negation/number guards.
- Browser checks passed unchanged original until Apply, apply/restore, stale-draft protection, clarification state, upstream failure, escaped HTML output, and mobile fit.
- Actual live request: `I WANT WATER PLEASE` → `I want water, please.` in 19.14 seconds after service restart. Original text remained unchanged until approval; restore returned it. No JavaScript page errors. No test message was saved.
- Runtime port 11434 is loopback-only and is not routed through the website. Private Python source and /api/generate returned 404. CPU and memory limits are set in the Ollama systemd drop-in.

## Quality and limits

Development probes preserved a request, a fragment, negation, a question, and a numeric quantity. An initial ambiguous draft was echoed unhelpfully; clarification instructions were revised and two additional ambiguous word lists requested clarification. An instruction-like draft also requested clarification rather than executing the instruction. These are small development checks, not an accuracy benchmark.

Suggestions may still change meaning. Lexical guards do not verify semantics. This model does not see signs, correct recognition errors, translate ASL grammar, or identify emotions. The website retains the original text, requires explicit Apply, and never automatically speaks or saves a suggestion. Existing recognition accuracy is unchanged.

Operations and official references: `ops/LLM.md`. Initial-load latency was about 21 seconds in development; warm short prompts around 3–5 seconds, with longer requests under contention. No general latency guarantee.
