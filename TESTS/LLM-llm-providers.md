# Tests for LLM: LLM providers, configuration, structured output, usage and cost

Spec: [SPECIFICATIONS/LLM-llm-providers.md](../SPECIFICATIONS/LLM-llm-providers.md)

| Test | Criterion | Kind | Input / fixture | Expected |
|---|---|---|---|---|
| `test_AC_LLM_01_example_config_loads` | AC-LLM-01 | unit | `config/llm-providers.example.yaml` | providers, modes, prices loaded |
| `test_AC_LLM_02_invalid_field_names_provider_field_and_line` | AC-LLM-02 | unit | `structured_output: xml` on line 8 | message has provider, field, `:8:` |
| `test_AC_LLM_02_missing_required_field` | AC-LLM-02 | unit | no `model` | names provider and field |
| `test_AC_LLM_02_bad_yaml_and_bad_top_level` | AC-LLM-02 | unit | broken YAML, list at top, missing file | `ProviderConfigError` |
| `test_AC_LLM_03_duplicate_names_rejected` | AC-LLM-03 | unit | two `a` providers | duplicate error |
| `test_AC_LLM_04_api_key_read_from_env` | AC-LLM-04 | unit | env var set | key returned |
| `test_AC_LLM_04_api_key_read_from_dotenv` | AC-LLM-04 | unit | `.env` in folder | key returned |
| `test_AC_LLM_05_saas_without_key_is_clear_error` | AC-LLM-05 | unit | SaaS, no key | `LlmError` names provider/variable |
| `test_AC_LLM_05_local_server_needs_no_key` | AC-LLM-05 | unit | localhost / 127.0.0.1 / 192.168.x | `None` |
| `test_AC_LLM_06_make_provider_by_adapter` | AC-LLM-06 | unit | three adapters | matching classes |
| `test_AC_LLM_07_json_schema_mode_sends_response_format` | AC-LLM-07 | unit | mock HTTP transport | request body |
| `test_AC_LLM_08_json_object_mode_describes_schema_in_prompt` | AC-LLM-08 | unit | mock HTTP | json_object + schema in prompt |
| `test_AC_LLM_09_prompt_mode_extracts_json_from_text` | AC-LLM-09 | unit | `<think>` + fenced JSON | parsed data |
| `test_AC_LLM_09_unparseable_text_gives_no_data` | AC-LLM-09 | unit | prose | `data is None` |
| `test_AC_LLM_09_extract_json_variants` | AC-LLM-09 | unit | strings | first JSON value |
| `test_AC_LLM_10_message_layout_and_temperature` | AC-LLM-10 | unit | mock HTTP | roles, content, temperature, max tokens param, extra body |
| `test_AC_LLM_11_usage_and_cost_with_cached_tokens` | AC-LLM-11 | unit | usage with cached tokens | 2.4 USD |
| `test_AC_LLM_11_cache_read_defaults_to_input_price` | AC-LLM-11 | unit | no cache price | input price used |
| `test_AC_LLM_12_request_caches_manuals_block_and_uses_native_schema` | AC-LLM-12 | unit | mock HTTP (Anthropic SDK) | blocks, cache_control, strict schema |
| `test_AC_LLM_12_effort_and_explicit_temperature` | AC-LLM-12 | unit | `extra.effort`, explicit temperature | sent |
| `test_AC_LLM_12_prompt_mode_puts_schema_in_instruction` | AC-LLM-12 | unit | prompt mode | no output_config |
| `test_AC_LLM_12_strict_schema_for_native_structured_output` | AC-LLM-12 | unit | schema with constraints | sanitized |
| `test_AC_LLM_13_falls_back_to_prompt_json_when_schema_rejected` | AC-LLM-13 | unit | 400 then 200 | retried without schema, remembered |
| `test_AC_LLM_13_other_bad_requests_are_not_retried` | AC-LLM-13 | unit | 400 "prompt is too long" | one request, `LlmError` |
| `test_AC_LLM_14_usage_includes_cache_read_and_write` | AC-LLM-14 | unit | cache tokens | 8.4 USD |
| `test_AC_LLM_14_default_cache_prices` | AC-LLM-14 | unit | no cache prices | 0.1× / 1.25× |
| `test_AC_LLM_15_http_error_becomes_readable_llm_error` | AC-LLM-15 | unit | 401 | message with status |
| `test_AC_LLM_15_connection_error_becomes_llm_error` | AC-LLM-15 | unit | connect error | "cannot connect" |
| `test_AC_LLM_15_rate_limit_is_retried_by_the_sdk` | AC-LLM-15 | unit | 429 then 200 | success after 2 requests |
| `test_AC_LLM_15_errors_become_readable_llm_errors` | AC-LLM-15 | unit | Claude 529 | message with status |
| `test_AC_LLM_15_client_uses_timeout_and_retries` | AC-LLM-15 | unit | config timeout / retries | SDK client settings |
| `test_AC_LLM_16_valid_first_try` | AC-LLM-16 | unit | FakeProvider | stats 1/1/0/0 |
| `test_AC_LLM_16_bare_list_is_wrapped` | AC-LLM-16 | unit | `[3]` | wrapped |
| `test_AC_LLM_17_invalid_output_retried_once_with_error` | AC-LLM-17 | unit | invalid then valid | retry prompt, same prefix |
| `test_AC_LLM_17_schema_mismatch_error_is_in_retry_prompt` | AC-LLM-17 | unit | wrong type | Pydantic error in prompt |
| `test_AC_LLM_18_still_invalid_raises_and_counts_failure` | AC-LLM-18 | unit | invalid twice | `LlmError`, failed=1, usage 2 calls |
| `test_AC_LLM_18_provider_error_counts_failure` | AC-LLM-18 | unit | provider raises | failed=1, no retry |
| `test_AC_LLM_19_duration_and_calls_set` | AC-LLM-19 | unit | mock HTTP | calls=1, duration>0 |
| `test_AC_LLM_20_refusal_raises_llm_error` | AC-LLM-20 | unit | `stop_reason: refusal` | `LlmError` |
| `test_AC_LLM_21_unknown_field_rejected` | AC-LLM-21 | unit | typo field on line 5 | error with line and field |
