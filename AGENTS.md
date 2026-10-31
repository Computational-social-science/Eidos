# Eidos working instructions

Eidos is a research-pipeline framework. Read README.md, docs/ORCHESTRATION.md, docs/HEALTH.md and docs/TAKEOVER-2026-10-31.md before changing orchestration or scientific gates. The current implementation uses deterministic chains and explicit human gates; it is not a LangGraph agent graph.

## Environment

Use the project environment, not shared Python. This host keeps source on an exFAT USB volume and the working environment on NVMe. In PowerShell:

```powershell
$env:UV_PROJECT_ENVIRONMENT = "$env:USERPROFILE\.venvs\eidos-py312"
$env:PATH = "$env:UV_PROJECT_ENVIRONMENT\Scripts;E:\2026-AI4S\tools\quarto\bin;" + $env:PATH
$env:QUARTO_BIN = "E:\2026-AI4S\tools\quarto\bin\quarto.exe"
$py = "$env:UV_PROJECT_ENVIRONMENT\Scripts\python.exe"
```

The local .python-version selects Python 3.12. Do not assume .venv is usable: exFAT does not support the directory junction this host would need. The old .venv-repro serves a separate paper-to-agent consumer; do not remove it casually.

Sync from uv.lock with `uv sync --frozen --extra dev --extra tracking --extra verifiers --extra browser`. Preserve pins when reconciling declarations; do not run a blanket upgrade. Use `uv lock --check` to detect drift. The core environment deliberately excludes generic LLM-evaluation extras until a consumer needs them.

## Verification

- Unit suite: `& $py -m pytest tests/ -q`.
- Real chains: `& $py tools/audit_chains.py`; an absent optional project checker is SKIP, never PASS.
- Three-format delivery: `& $py tools/check_render.py --json`.
- Live state: `& $py tools/health.py --json`; require fresh samples and increasing seq, not just overall=OK.
- Consumer checks: `& $py -m framework.project check <name>`; positive consumers and deliberate negative controls have different expected outcomes.
- Browser/site checks follow the repository's existing commands and committed evidence contracts.

Keep generated runtime evidence distinct from code changes. docs/NUMERICS.json and docs/pipeline.json were already dirty at takeover; do not reset unrelated changes. Never call SKIP a passed chain, or promote a model judgement into a scientific gate without its required validation.

## Scientific qualification

The existing Softmax Collapse/Cancellation Paper2Agent conversion is under reference/barron2026_agent and reference/reproduction/barron2026/mcp; reuse it rather than creating a duplicate agent. Read docs/QUALITY-2026-10-31.md and docs/CASE-SOFTMAX.md for the accepted evidence and limits.

For a numerical consumer, declare `numerics: required` in its registry and run `python tools/audit_numerics.py --projects`. This runs built-in qualification and heuristic consumer screening; it does not certify the consumer backend. Probe the actual execution path against independent references, preserve input dtype, check relative gradients without an absolute floor, and include broken controls. Do not replace gradient checks with finite loss or sum-to-one checks. Record source/lock/data/config versions, seeds (or why none apply), device and dtype. AMP/bfloat16 and higher-order backward remain unqualified until separately tested.

The site case and exports share tools/numerics_case.py. Build with tools/build_site.py; produce HTML/PDF/DOCX via `python tools/numerics_case.py --render`. Never hand-edit site/index.html or claim paper training outcomes from these kernel tests.

## Local operations

scripts/eidos-monitor.cmd reads the ignored scripts/monitor.env. That file selects the local interpreter and Quarto path. The existing Startup entry already calls this script; do not register a second monitor. The supervisor has a PID lock. Services bind to loopback. Never log credential-bearing launch commands. The current user proxy is http://127.0.0.1:7890; localhost must bypass it. Verify the listener before troubleshooting package downloads.

File accepted findings and operational changes in project documentation. Do not commit or push automatically unless requested.
