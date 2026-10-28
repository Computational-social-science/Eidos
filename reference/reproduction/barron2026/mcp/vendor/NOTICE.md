# Vendored third-party file

`verify_mcp_server.py` is copied unmodified from **Paper2Agent** (MIT), because re-verifying the MCP
server should not require cloning a repository into a scratch directory on this machine.

| field | value |
|---|---|
| upstream | https://github.com/jmiao24/Paper2Agent |
| path | `skills/paper2agent/paper2mcp/scripts/verify_mcp_server.py` |
| commit | `8c2d059165ef8cdcb70dbea76655b9c2b55b38e6` (2026-09-17) |
| sha256 | `22a2de7f8e25f50262475acf9f86438e802b040a77cbcd617de03ec567990a73` |
| licence | MIT — full text in `LICENSE` next to this file |

Do not patch it: the value of this file is that it is the upstream check, not ours. If it needs to
change, update the copy and the hash together, and say so in the commit message.

Re-run:

```bash
.venv-repro/Scripts/python.exe reference/reproduction/barron2026/mcp/vendor/verify_mcp_server.py \
  --server reference/reproduction/barron2026/mcp/server.py \
  --expected reference/reproduction/barron2026/mcp/expected.json \
  --cases reference/reproduction/barron2026/mcp/cases.json \
  --require-all-tools --report reference/reproduction/barron2026/mcp/verify.json \
  --cwd reference/reproduction/barron2026/mcp
```
