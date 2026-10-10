# LLM: LLM providers, configuration, structured output, usage and cost

- **Status:** Implemented
- **Approval:** Approved by the owner's go-ahead on 2026-10-10; to be validated in owner testing.
- **Related ADRs:** ADR-0003, ADR-0004, ADR-0006, ADR-0011
- **Depends on:** FIND (domain `Usage`, `LlmCallStats`)

## Purpose
Reviewers want to use any LLM, SaaS or local, without changing code. This feature reads the provider list
from `config/llm-providers.yaml`, finds API keys in the environment, talks to OpenAI-compatible endpoints and
to the native Claude API, always returns validated structured JSON (or a clear error), and reports tokens,
cost and time for every call.

## User stories
- As a reviewer, I want to add a model by editing a YAML file, so that I do not need a developer.
- As a reviewer, I want a clear message naming the provider, field and line when my config is wrong.
- As a reviewer, I want my API keys kept out of files that might be committed.
- As a reviewer using a small local model, I want the app to cope with weak JSON output.
- As a cost-conscious reviewer, I want tokens (including cached tokens) and estimated cost per run.

## Behaviour

### Config file
`load_providers(path) -> list[ProviderConfig]` reads `providers:` (a list of mappings). Fields are those of
`ProviderConfig` (`umr.llm.base`); unknown fields are errors (catches typos). Errors raise
`ProviderConfigError` (an `LlmError`) whose message is `<file>:<line>: provider '<name>': field '<field>': <reason>`.
Duplicate names, an empty list, invalid YAML and a missing file are errors. Before loading, `.env` files in the
config folder, its parent (repo root) and the current folder are loaded without overriding set variables.

`config` keys documented in `config/llm-providers.example.yaml`; adapter options go under `extra`:

| Adapter | `extra` key | Meaning |
|---|---|---|
| openai-compatible | `max_tokens_param` | `max_tokens` (default) or `max_completion_tokens` (OpenAI reasoning models) |
| openai-compatible | `extra_body` | dict merged into every request (e.g. `num_ctx` for Ollama) |
| both | `max_retries` | SDK retries on 408/409/429/5xx and connection errors (default 2) |
| anthropic | `effort` | `output_config.effort` |

### API keys
`get_api_key(cfg)` returns the value of the variable named in `api_key_env`. A local endpoint (localhost,
loopback, private network, `*.local`) may have no key (returns `None`). A SaaS endpoint (including the default
OpenAI and Anthropic endpoints) without a key raises an `LlmError` naming the provider and the variable.

### Factory
`make_provider(cfg, **kwargs)` returns `OpenAICompatibleProvider`, `AnthropicProvider` or `FakeProvider` by
`cfg.adapter`; `client=` injects an SDK client (tests).

### OpenAI-compatible adapter
Chat Completions through the official `openai` SDK with `base_url`, `timeout=timeout_s`.
Messages: `system`, then `user` = `cache_prefix + "\n\n" + prompt` (prefix first, so automatic prefix caching
works). `temperature` only when not null. Structured output by `structured_output`:

| Mode | Request | Prompt |
|---|---|---|
| `json_schema` | `response_format={"type":"json_schema","json_schema":{"name","schema","strict":false}}` | unchanged |
| `json_object` | `response_format={"type":"json_object"}` | schema appended after the instruction |
| `prompt` | none | schema appended after the instruction |

The answer text is parsed tolerantly in every mode: `<think>`/`<thinking>` blocks removed, ```json fences
stripped, otherwise the first JSON object/array in the text. Unparseable text gives `data=None` (the
validation layer then retries).

### Native Claude adapter
`anthropic` SDK Messages API: `system` text block; one user message with two content blocks: the manuals
(`cache_prefix`) with `cache_control: {"type": "ephemeral"}`, then the instruction. With `json_schema` the
request has `output_config.format = {"type":"json_schema","schema": strict_schema(schema)}` (every object gets
`additionalProperties: false`; numeric/string/array constraints are removed and still enforced by Pydantic).
If the API rejects the structured-output request with HTTP 400 mentioning format/schema, the call is repeated
once with the schema in the prompt, and the provider remembers to use prompt mode from then on. Other modes put
the schema in the prompt. `temperature` is sent only when set explicitly in the config file. A `refusal` stop
reason is an `LlmError`. Text blocks are joined; thinking blocks are ignored.

### Errors, retries, timing
Both adapters use the SDK's built-in retries and the configured timeout; HTTP, timeout and connection failures
raise `LlmError` with the provider name, the HTTP status and the server's message. Each call measures
`duration_s` and sets `calls=1`.

### Usage and cost
`Usage.input_tokens` is the whole prompt (OpenAI `prompt_tokens`; Claude `input_tokens + cache_read + cache_creation`),
`cached_tokens` the tokens read from cache. Cost (USD) = uncached input × `input` + output × `output` + cache
reads × `cache_read` + cache writes × `cache_write`, prices per million tokens. Missing cache prices default to
the input price (OpenAI-compatible) or 0.1× / 1.25× the input price (Claude).

### Validated structured output
`complete_validated(provider, *, system, cache_prefix, prompt, model_cls, schema_name="findings", stats=None,
usage=None) -> ValidatedResult(data, usage, valid_first_try, retried)` calls the provider with
`model_cls.model_json_schema()` and validates with Pydantic (a bare list is wrapped into a single-field model).
If invalid, it calls once more with the same prefix and the prompt plus `YOUR PREVIOUS ANSWER WAS INVALID.
<error>`; still invalid raises `LlmError`. `stats` (`LlmCallStats`) gets `calls += 1` and exactly one of
`valid_first_try`, `retried`, `failed`; `usage` receives every call's usage, also when the call fails.

### Call log
Every request and response is written to `~/.user-manual-reviewer/logs/llm-calls-YYYY-MM-DD.jsonl`
(folder from `UMR_LOG_DIR`), one JSON object per line, linked by `call_id`: `request` (URL, model, full body),
then `response` (raw text, finish reason, usage, full SDK response) or `error` (type, message, HTTP status,
server response body, which is where local servers such as LM Studio and Ollama explain what went wrong).
Only bodies are logged, never headers, so API keys stay out; keys named `api_key`, `authorization` or
`x-api-key` are redacted anywhere in a body. A failure to write the log is a warning, never a failed check.
Short summaries go to the `umr.llm` Python logger at INFO (`umr -v ...` prints them; the GUI run log shows
them). `umr providers --test NAME` sends one tiny request to check URL, model and JSON mode.

## Acceptance criteria
| Id | Given | When | Then |
|---|---|---|---|
| AC-LLM-01 | the example config | `load_providers` | all providers load with their adapter, mode, context, prices |
| AC-LLM-02 | a provider with an invalid or missing field, invalid YAML, no `providers` list or a missing file | `load_providers` | `ProviderConfigError` naming file, line, provider and field |
| AC-LLM-03 | two providers with the same name | `load_providers` | error "duplicate provider name" |
| AC-LLM-04 | `api_key_env` names a variable set in the environment or in `.env` | `get_api_key` | the key is returned |
| AC-LLM-05 | a SaaS endpoint with no key / a local endpoint with no key | `get_api_key` | clear `LlmError` / `None` |
| AC-LLM-06 | a config per adapter | `make_provider` | the matching provider class with that name |
| AC-LLM-07 | `structured_output: json_schema` | OpenAI-compatible call | `response_format` json_schema with name, schema, `strict: false` |
| AC-LLM-08 | `json_object` | call | `response_format` json_object and the schema in the prompt after the instruction |
| AC-LLM-09 | `prompt` mode, an answer with `<think>`, fences or prose | call | no `response_format`; the JSON is extracted; unparseable gives `data=None` |
| AC-LLM-10 | any call | OpenAI-compatible request | messages system, user = prefix + blank line + prompt; temperature only if not null; configurable max-tokens parameter and extra body |
| AC-LLM-11 | a response with prompt, completion and cached tokens | call | usage fields and cost from `price_per_mtok` |
| AC-LLM-12 | the Claude adapter | call | system block; manuals block with ephemeral `cache_control` before the instruction block; `output_config.format` with a strict schema; temperature only if set explicitly; effort from `extra` |
| AC-LLM-13 | the API rejects native structured output with a 400 about the format | call | retried once with the schema in the prompt and prompt mode remembered; other 400s are not retried |
| AC-LLM-14 | a Claude response with cache read and write tokens | call | input/cached tokens and cost including cache prices (defaults 0.1× / 1.25×) |
| AC-LLM-15 | an HTTP error, connection error or 429 | call | readable `LlmError` with provider and status; 429 retried by the SDK; client timeout and retries from config |
| AC-LLM-16 | a valid answer | `complete_validated` | parsed model, `valid_first_try`, stats calls=1 valid_first_try=1 |
| AC-LLM-17 | an invalid first answer and a valid second | `complete_validated` | exactly one retry with the error appended and the same prefix; stats retried=1 |
| AC-LLM-18 | two invalid answers, or a provider error | `complete_validated` | `LlmError`; stats failed=1; usage of both calls recorded |
| AC-LLM-19 | any adapter call | call | `duration_s` > 0 and `calls` = 1 |
| AC-LLM-20 | Claude stops with `refusal` | call | `LlmError` "declined" |
| AC-LLM-21 | an unknown field (typo) in a provider | `load_providers` | error naming the field and its line |
| AC-LLM-22 | any call, either adapter | before it is sent | a `request` entry in the call log with call id, provider, full URL, model and the full request body |
| AC-LLM-23 | a successful call | after it returns | a `response` entry with the same call id, raw text, finish reason, duration and the full response |
| AC-LLM-24 | an HTTP error, timeout or connection error | after it fails | an `error` entry with the status code and the server's response body; the CLI names the log file |
| AC-LLM-25 | any call | it is logged | one-line summaries on the `umr.llm` logger, printed by `umr -v` and shown in the GUI run log |
| AC-LLM-26 | `umr providers --test NAME` | run | one tiny structured request; prints OK with the answer, or FAILED with the error and the log file |
| AC-LLM-27 | a request carrying an API key | logged | the key never appears in the log; `UMR_LLM_LOG=0` turns the file log off |

## Examples
```yaml
providers:
  - name: local-ollama
    adapter: openai-compatible
    base_url: http://localhost:11434/v1
    model: qwen3:32b
    structured_output: json_object
```
`load_providers` on `    strutured_output: prompt` at line 5 gives
`llm-providers.yaml:5: provider 'typo': unknown field 'strutured_output' (known: ...)`.

## Out of scope
- Streaming responses, Batches API, Claude on Bedrock/Vertex/Foundry clients.
- Live calls in the default test suite (tests use mocked HTTP transports and `FakeProvider`).
- Per-model price lookup; prices are user-maintained.

## Open questions
- Should a provider fall back automatically from `json_schema` to `json_object` on OpenAI-compatible servers
  that reject `response_format` json_schema? Today the error message is shown and the user changes the mode.
