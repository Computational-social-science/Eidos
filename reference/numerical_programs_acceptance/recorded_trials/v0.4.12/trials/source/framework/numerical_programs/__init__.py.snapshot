"""Bounded scalar formula/JSON execution for research tools.

Accept native NumPy float32/64 scalars and 0D arrays, including finite negative
and zero inputs. All selected intermediates must be finite. Source/JSON limits
and immutable values restrict expression execution; they are not an OS sandbox.

Gradients are supplied formulas, not automatically derived or scientifically
verified derivatives. Independent domain/accuracy checks remain the caller's job.
"""
from ._compiler import MAX_SOURCE_BYTES, compile_formulas
from ._json import MAX_BYTES
from ._language import MAX_DEPTH, MAX_NODES, ScalarProgram, execute, parse_program

__all__ = ['ScalarProgram', 'compile_formulas', 'parse_program', 'execute',
           'MAX_SOURCE_BYTES', 'MAX_BYTES', 'MAX_DEPTH', 'MAX_NODES']
