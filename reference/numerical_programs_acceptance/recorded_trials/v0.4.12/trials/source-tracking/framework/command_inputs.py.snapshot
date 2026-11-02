"""Direct Python argv entry binding shared by SDK execution and observation."""

from pathlib import Path
import re


def python_entry(
    command: list[str],
    declared_inputs: list[str],
    label: str = "command",
    input_field: str = "inputs",
) -> str | None:
    if not command:
        return None
    if Path(command[0]).suffix.lower() in {".py", ".pyw"}:
        return command[0]
    if not (
        command[0] == "{python}"
        or re.fullmatch(
            r"(?:pythonw?|pypy)(?:\d+(?:\.\d+)*)?(?:\.exe)?",
            Path(command[0]).name,
            re.I,
        )
    ):
        return None
    args = iter(command[1:])
    for arg in args:
        if arg.startswith("-m"):
            if not declared_inputs:
                raise ValueError(
                    "module-mode " + label + " requires explicit " + input_field
                )
            return None
        if arg.startswith("-c") or arg == "-":
            return None
        if arg in {"-X", "-W", "--check-hash-based-pycs"}:
            if next(args, None) is None:
                raise ValueError("Python " + label + " option has no value")
        elif arg.startswith(("-X", "-W", "--check-hash-based-pycs=")):
            continue
        elif arg == "--":
            entry = next(args, None)
            if entry is None:
                raise ValueError("Python " + label + " has no entry after --")
            return entry
        elif arg.startswith("-"):
            if len(arg) < 2 or any(c not in "bBdEiIOPqRsSuvVx" for c in arg[1:]):
                raise ValueError(
                    "cannot bind unknown Python " + label + " option: " + arg
                )
        else:
            return arg
    return None
