"""tex2pdf: A minimal CLI tool for compiling LaTeX files to PDF with structured error reporting."""

from __future__ import annotations

from tex2pdf.core import compile_tex
from tex2pdf.models import CompileResult, Diagnostic, EngineConfig

__version__ = "0.1.0"
__all__ = ["compile_tex", "CompileResult", "Diagnostic", "EngineConfig"]
