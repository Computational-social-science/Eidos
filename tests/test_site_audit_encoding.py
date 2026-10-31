"""Diagnostic Unicode and malformed child bytes must not hide an audit verdict."""

import io
import sys
from contextlib import redirect_stdout

import pytest

from tools import audit_site


@pytest.mark.parametrize("code", [0, 7])
def test_utf8_child_diagnostics_survive_a_strict_gbk_terminal(code):
    buffer = io.BytesIO()
    terminal = io.TextIOWrapper(buffer, encoding="gbk", errors="strict", write_through=True)
    command = [sys.executable, "-c", f"import sys; print(chr(0x1f9ea)); raise SystemExit({code})"]
    with redirect_stdout(terminal):
        passed, output = audit_site.run(command, "unicode diagnostic")
    assert passed is (code == 0)
    assert "\U0001f9ea" in output
    if code:
        assert b"\\U0001f9ea" in buffer.getvalue()


def test_malformed_child_bytes_preserve_failure_without_print_crash():
    buffer = io.BytesIO()
    terminal = io.TextIOWrapper(buffer, encoding="gbk", errors="strict", write_through=True)
    command = [sys.executable, "-c", "import sys; sys.stdout.buffer.write(b'bad\\xff'); raise SystemExit(1)"]
    with redirect_stdout(terminal):
        passed, output = audit_site.run(command, "invalid byte diagnostic")
    assert passed is False
    assert output == "bad\ufffd"
    assert b"bad\\ufffd" in buffer.getvalue()
