# Working on this repository

- Read `docs/architecture/README.md` and `docs/adr/README.md` before changing anything.
- Follow `SDD_PROCESS.md`: no code for a feature without an `Approved` spec; test names contain the acceptance criterion id.
- Layers depend downwards only (see architecture section 4); only `umr.gui` imports PySide6.
- Never put API keys in files; use the environment variables named in `config/llm-providers.yaml`.
- Never open `samples/shopflow/ANSWER_KEY.md` or `expected-findings.yaml` as input to a review; they are the evaluation answer key.
