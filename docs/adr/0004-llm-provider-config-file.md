# ADR-0004: LLM providers in a YAML config file, keys in environment variables

- **Status:** Proposed
- **Date:** 2026-10-10

## Context
Users must be able to add LLMs without changing code, including local models, and choose any two for a side-by-side comparison.

## Decision
Providers are listed in `config/llm-providers.yaml`:

```yaml
providers:
  - name: claude-sonnet            # shown in the GUI
    adapter: anthropic             # anthropic | openai-compatible
    model: claude-sonnet-5-5
    api_key_env: ANTHROPIC_API_KEY
    context_tokens: 1000000
    max_concurrency: 4
    price_per_mtok: { input: 2.00, output: 10.00, cache_read: 0.20 }

  - name: gpt
    adapter: openai-compatible
    base_url: https://api.openai.com/v1
    model: gpt-5
    api_key_env: OPENAI_API_KEY
    structured_output: json_schema # json_schema | json_object | prompt

  - name: gemini
    adapter: openai-compatible
    base_url: https://generativelanguage.googleapis.com/v1beta/openai/
    model: gemini-2.5-pro
    api_key_env: GEMINI_API_KEY

  - name: local-qwen
    adapter: openai-compatible
    base_url: http://localhost:11434/v1   # Ollama
    model: qwen3:32b
    structured_output: json_object
    context_tokens: 32768
```

The file is validated with Pydantic at start-up; errors name the line and field. Keys are read from the environment, optionally loaded from a git-ignored `.env`. The repository ships `config/llm-providers.example.yaml`.

## Consequences
- Secrets never land in the config file or in git.
- `context_tokens` and `structured_output` let the app adapt to weaker or smaller local models.
- Prices are user-maintained; cost figures are estimates.

## Alternatives considered
- **GUI-only settings** – harder to share, version and review; a GUI editor can be added later on top of the same file.
- **Keys in the config file** – too easy to commit by accident.
- **OS keychain** – better security, more platform work; can be added later as another key source.
