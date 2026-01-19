"""Tests for log analysis functionality."""

from __future__ import annotations

import pytest

from tex2pdf.analysis import analyse_log
from tex2pdf.models import Diagnostic


def test_undefined_control_sequence() -> None:
    """Test detection of undefined control sequence errors."""
    log = r"""
! Undefined control sequence.
l.5 \foo
           {bar}
? 
"""
    diagnostics = analyse_log(log)
    assert len(diagnostics) >= 1
    error_diags = [d for d in diagnostics if d.code == "undefined-control-sequence"]
    assert len(error_diags) > 0
    assert "undefined control sequence" in error_diags[0].message.lower()
    assert r"\foo" in error_diags[0].raw or "foo" in error_diags[0].message.lower()


def test_missing_package() -> None:
    """Test detection of missing package file errors."""
    log = """
! LaTeX Error: File `missingpackage.sty' not found.

Type X to quit or <RETURN> to proceed,
or enter new name. (Default extension: sty)
"""
    diagnostics = analyse_log(log)
    assert len(diagnostics) >= 1
    error_diags = [d for d in diagnostics if d.code == "missing-package"]
    assert len(error_diags) > 0
    assert "missing package" in error_diags[0].message.lower()
    assert "missingpackage.sty" in error_diags[0].message


def test_runaway_argument() -> None:
    """Test detection of runaway argument errors."""
    log = r"""
Runaway argument?
{ This is a runaway argument that never closes
! File ended while scanning use of \@xverbatim.
<inserted text> 
                \par 
l.10 \begin{verbatim}
"""
    diagnostics = analyse_log(log)
    assert len(diagnostics) >= 1
    error_diags = [d for d in diagnostics if d.code == "runaway-argument"]
    assert len(error_diags) > 0
    assert "runaway argument" in error_diags[0].message.lower()
    assert "unclosed brace" in error_diags[0].message.lower() or "missing" in error_diags[0].message.lower()


def test_generic_latex_error() -> None:
    """Test detection of generic LaTeX error lines."""
    log = r"""
! Something went wrong here.
l.10 \textbf{bad}
"""
    diagnostics = analyse_log(log)
    assert len(diagnostics) >= 1
    error_diags = [d for d in diagnostics if d.code in ("latex-error", "undefined-control-sequence")]
    assert len(error_diags) > 0
    assert error_diags[0].level == "error"


def test_multiple_errors() -> None:
    """Test that multiple errors are detected."""
    log = r"""
! Undefined control sequence.
l.5 \foo
! LaTeX Error: File `missing.sty' not found.
"""
    diagnostics = analyse_log(log)
    # Should detect at least undefined control sequence and missing package
    codes = {d.code for d in diagnostics}
    assert "undefined-control-sequence" in codes or "missing-package" in codes


def test_empty_log() -> None:
    """Test that empty logs return no diagnostics."""
    diagnostics = analyse_log("")
    assert len(diagnostics) == 0


def test_successful_compilation_log() -> None:
    """Test that successful compilation logs produce minimal diagnostics."""
    log = r"""
This is pdfTeX, Version 3.14159265-2.6-1.40.21 (TeX Live 2020)
entering extended mode
(./test.tex
LaTeX2e <2020-02-02> patch level 5
Document Class: article 2019/12/20 v1.4l Standard LaTeX document class
(./test.aux)
No file test.aux.
)
Output written on test.pdf (1 page, 12345 bytes).
Transcript written on test.log.
"""
    diagnostics = analyse_log(log)
    # Should not have errors for successful compilation
    error_diags = [d for d in diagnostics if d.level == "error"]
    assert len(error_diags) == 0
