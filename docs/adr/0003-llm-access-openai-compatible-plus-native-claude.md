# ADR-0003: OpenAI-compatible API as the standard, plus an optional native Claude adapter

- **Status:** Proposed
- **Date:** 2026-10-10

## Context
The owner wants to use various LLMs: SaaS (Claude, ChatGPT, Gemini, ...) and locally hosted models. Standard APIs are preferred unless a vendor-specific API offers compelling features.

## Decision
1. The default adapter, `OpenAICompatibleProvider`, uses the **OpenAI Chat Completions API** with a configurable base URL. This is the de facto standard: OpenAI, Google Gemini (OpenAI-compatible endpoint), Mistral, Groq, OpenRouter and local servers (Ollama, LM Studio, vLLM, llama.cpp server) all accept it.
2. An optional `AnthropicProvider` uses the **native Claude Messages API**, because it gives two features that matter for this application:
   - **Explicit prompt caching**: every check of a run sends the same manuals; caching them as a prefix cuts input cost and latency substantially.
   - **Native structured outputs** with JSON schema, so findings arrive in the expected shape.
3. Both implement the same `LlmProvider` interface. Checks never know which adapter they use.
4. No other vendor-specific adapters are added unless a new ADR shows a comparable benefit.

## Consequences
- Adding a model is a config change, not a code change, for any OpenAI-compatible endpoint.
- Claude can still be used through its OpenAI-compatible endpoint without the native adapter, at the cost of caching and full feature support.
- Two adapters to maintain and test; both are covered by recorded-response tests.

## Alternatives considered
- **OpenAI-compatible only** – loses Claude's explicit caching, which is a large share of the cost for repeated checks over the same manuals.
- **A native adapter per vendor** – more code for little gain; Gemini and OpenAI cache automatically through the compatible API.
- **A multi-provider library (for example LiteLLM)** – one more large dependency between us and the APIs; harder to reason about and to audit.
