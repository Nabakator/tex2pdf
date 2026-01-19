"""Core compilation logic for tex2pdf."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Optional

from tex2pdf.analysis import analyse_log
from tex2pdf.models import CompileResult, Diagnostic, EngineConfig


def _find_engine_executable(engine_name: str) -> Optional[str]:
    """Find the executable path for a given LaTeX engine.

    Args:
        engine_name: Name of the engine ('tectonic' or 'latexmk')

    Returns:
        Path to the executable if found, None otherwise
    """
    return shutil.which(engine_name)


def _get_default_engine() -> str:
    """Determine the default LaTeX engine to use.

    Returns:
        Engine name ('tectonic' or 'latexmk'), preferring tectonic
    """
    if _find_engine_executable("tectonic"):
        return "tectonic"
    if _find_engine_executable("latexmk"):
        return "latexmk"
    return "tectonic"  # Default fallback, will fail later if not found


def _run_tectonic(
    tex_path: Path,
    outdir: Path,
    timeout: Optional[int],
) -> tuple[int, str, Path]:
    """Run tectonic to compile a LaTeX file.

    Args:
        tex_path: Path to the input .tex file
        outdir: Directory for output files
        timeout: Maximum execution time in seconds (None for no timeout)

    Returns:
        Tuple of (return_code, combined_log, pdf_path)

    Raises:
        FileNotFoundError: If tectonic executable is not found
    """
    tectonic_exe = _find_engine_executable("tectonic")
    if not tectonic_exe:
        raise FileNotFoundError("tectonic executable not found on PATH")

    # Ensure output directory exists
    outdir.mkdir(parents=True, exist_ok=True)

    # Build command: tectonic --outdir=OUTDIR input.tex
    cmd = [
        tectonic_exe,
        str(tex_path),
        f"--outdir={outdir}",
    ]

    pdf_path = outdir / f"{tex_path.stem}.pdf"

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=tex_path.parent,
        )
        log = result.stdout + result.stderr
        return result.returncode, log, pdf_path
    except subprocess.TimeoutExpired:
        return 1, f"Compilation timed out after {timeout} seconds", pdf_path
    except FileNotFoundError:
        raise


def _run_latexmk(
    tex_path: Path,
    outdir: Path,
    timeout: Optional[int],
) -> tuple[int, str, Path]:
    """Run latexmk to compile a LaTeX file.

    Args:
        tex_path: Path to the input .tex file
        outdir: Directory for output files
        timeout: Maximum execution time in seconds (None for no timeout)

    Returns:
        Tuple of (return_code, combined_log, pdf_path)

    Raises:
        FileNotFoundError: If latexmk executable is not found
    """
    latexmk_exe = _find_engine_executable("latexmk")
    if not latexmk_exe:
        raise FileNotFoundError("latexmk executable not found on PATH")

    # Ensure output directory exists
    outdir.mkdir(parents=True, exist_ok=True)

    # Build command: latexmk -pdf -interaction=nonstopmode -halt-on-error -outdir=OUTDIR input.tex
    cmd = [
        latexmk_exe,
        "-pdf",
        "-interaction=nonstopmode",
        "-halt-on-error",
        f"-outdir={outdir}",
        str(tex_path.name),
    ]

    pdf_path = outdir / f"{tex_path.stem}.pdf"

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=tex_path.parent,
        )
        log = result.stdout + result.stderr
        return result.returncode, log, pdf_path
    except subprocess.TimeoutExpired:
        return 1, f"Compilation timed out after {timeout} seconds", pdf_path
    except FileNotFoundError:
        raise


def compile_tex(
    tex_path: Path,
    outdir: Path,
    engine: EngineConfig,
    timeout: Optional[int] = None,
) -> CompileResult:
    """Compile a LaTeX file to PDF using the specified engine.

    Args:
        tex_path: Path to the input .tex file
        outdir: Directory for output files (will be created if missing)
        engine: Engine configuration
        timeout: Maximum execution time in seconds (None for no timeout)

    Returns:
        CompileResult containing success status, PDF path, log, and diagnostics
    """
    # Validate input file
    if not tex_path.exists():
        return CompileResult(
            success=False,
            engine=engine.name,
            diagnostics=[
                Diagnostic(
                    level="error",
                    code="file-not-found",
                    message=f"Input file not found: {tex_path}",
                    raw=f"File not found: {tex_path}",
                )
            ],
        )

    if not tex_path.is_file():
        return CompileResult(
            success=False,
            engine=engine.name,
            diagnostics=[
                Diagnostic(
                    level="error",
                    code="invalid-input",
                    message=f"Input path is not a file: {tex_path}",
                    raw=f"Not a file: {tex_path}",
                )
            ],
        )

    # Run the appropriate engine
    try:
        if engine.name == "tectonic":
            return_code, log, pdf_path = _run_tectonic(tex_path, outdir, timeout)
        elif engine.name == "latexmk":
            return_code, log, pdf_path = _run_latexmk(tex_path, outdir, timeout)
        else:
            return CompileResult(
                success=False,
                engine=engine.name,
                diagnostics=[
                    Diagnostic(
                        level="error",
                        code="unsupported-engine",
                        message=f"Unsupported engine: {engine.name}",
                        raw=f"Engine {engine.name} is not supported",
                    )
                ],
            )
    except FileNotFoundError as e:
        return CompileResult(
            success=False,
            engine=engine.name,
            log=str(e),
            diagnostics=[
                Diagnostic(
                    level="error",
                    code="engine-not-found",
                    message=f"LaTeX engine '{engine.name}' not found on PATH",
                    raw=str(e),
                )
            ],
        )
    except Exception as e:
        return CompileResult(
            success=False,
            engine=engine.name,
            log=str(e),
            diagnostics=[
                Diagnostic(
                    level="error",
                    code="compilation-error",
                    message=f"Unexpected error during compilation: {e}",
                    raw=str(e),
                )
            ],
        )

    # Check for timeout in log
    if "timed out" in log.lower():
        return CompileResult(
            success=False,
            engine=engine.name,
            return_code=return_code,
            log=log,
            diagnostics=[
                Diagnostic(
                    level="error",
                    code="timeout",
                    message=f"Compilation timed out after {timeout} seconds",
                    raw=log,
                )
            ],
        )

    # Analyze log for diagnostics
    diagnostics = analyse_log(log)

    # Determine success: return code 0 and PDF exists
    success = return_code == 0 and pdf_path.exists()

    # If compilation failed but we have no diagnostics, add a generic one
    if not success and not diagnostics:
        diagnostics.append(
            Diagnostic(
                level="error",
                code="compilation-failed",
                message="Compilation failed. Check the log for details.",
                raw=log[-500:] if len(log) > 500 else log,  # Last 500 chars as sample
            )
        )

    return CompileResult(
        success=success,
        pdf_path=pdf_path if pdf_path.exists() else None,
        log=log,
        diagnostics=diagnostics,
        engine=engine.name,
        return_code=return_code,
        workdir=tex_path.parent,
    )
