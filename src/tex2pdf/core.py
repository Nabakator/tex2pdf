"""Core compilation logic for tex2pdf."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from tex2pdf.analysis import analyse_log
from tex2pdf.models import CompileResult, Diagnostic, EngineConfig

_BIBLATEX_PATTERN = re.compile(
    r"\\usepackage(?:\[[^\]]*\])?\{biblatex\}|"
    r"\\addbibresource\{[^}]+\}|"
    r"\\printbibliography\b",
    re.MULTILINE,
)
_BIBER_VERSION_MISMATCH_PATTERN = re.compile(
    r"Found biblatex control file version [0-9.]+, expected version [0-9.]+\.\s*"
    r"This means that your biber \([^)]+\) and biblatex \([^)]+\) versions are incompatible\.",
    re.MULTILINE,
)
_AUXILIARY_SUFFIXES = (
    ".aux",
    ".bbl",
    ".bcf",
    ".blg",
    ".fdb_latexmk",
    ".fls",
    ".log",
    ".out",
    ".run.xml",
)


def _find_engine_executable(engine_name: str) -> Optional[str]:
    """Find the executable path for a given LaTeX engine.

    Args:
        engine_name: Name of the engine ('tectonic' or 'latexmk')

    Returns:
        Path to the executable if found, None otherwise
    """
    return shutil.which(engine_name)


def _document_uses_biblatex(tex_path: Path) -> bool:
    """Return True when the TeX source appears to use biblatex/biber."""
    try:
        source = tex_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False

    return bool(_BIBLATEX_PATTERN.search(source))


def _has_biber_version_mismatch(log: str) -> bool:
    """Detect a biber/biblatex version mismatch in compilation output."""
    return bool(_BIBER_VERSION_MISMATCH_PATTERN.search(log))


def _cleanup_auxiliary_files(tex_path: Path, outdir: Path) -> None:
    """Remove known LaTeX auxiliary files for a document from the output directory."""
    for suffix in _AUXILIARY_SUFFIXES:
        aux_path = outdir / f"{tex_path.stem}{suffix}"
        try:
            aux_path.unlink()
        except FileNotFoundError:
            continue


def _get_default_engine(tex_path: Optional[Path] = None) -> str:
    """Determine the default LaTeX engine to use.

    Returns:
        Engine name ('tectonic' or 'latexmk'), preferring the most compatible choice
    """
    tectonic_exe = _find_engine_executable("tectonic")
    latexmk_exe = _find_engine_executable("latexmk")

    # Prefer latexmk for biblatex documents because tectonic may delegate to a
    # system biber whose version is out of sync with tectonic's bundled biblatex.
    if tex_path and latexmk_exe and _document_uses_biblatex(tex_path):
        return "latexmk"
    if tectonic_exe:
        return "tectonic"
    if latexmk_exe:
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
    keep_aux: bool = False,
) -> CompileResult:
    """Compile a LaTeX file to PDF using the specified engine.

    Args:
        tex_path: Path to the input .tex file
        outdir: Directory for output files (will be created if missing)
        engine: Engine configuration
        timeout: Maximum execution time in seconds (None for no timeout)
        keep_aux: Keep auxiliary files in the output directory after success

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
    result_diagnostics: list[Diagnostic] = []
    used_engine_name = engine.name
    analysis_log = ""
    try:
        if engine.name == "tectonic":
            return_code, log, pdf_path = _run_tectonic(tex_path, outdir, timeout)
            analysis_log = log

            if return_code != 0 and _has_biber_version_mismatch(log):
                try:
                    retry_return_code, retry_log, retry_pdf_path = _run_latexmk(
                        tex_path,
                        outdir,
                        timeout,
                    )
                except FileNotFoundError:
                    pass
                else:
                    used_engine_name = "latexmk"
                    result_diagnostics.append(
                        Diagnostic(
                            level="info",
                            code="engine-fallback",
                            message=(
                                "Tectonic hit a biblatex/biber version mismatch; "
                                "retried with latexmk."
                            ),
                            raw="tectonic -> latexmk",
                        )
                    )
                    log = (
                        "note: tectonic failed with a biblatex/biber version mismatch; "
                        "retrying with latexmk.\n\n"
                        f"{log}\n\n"
                        "note: latexmk retry log follows.\n\n"
                        f"{retry_log}"
                    )
                    analysis_log = retry_log if retry_return_code == 0 else log
                    return_code = retry_return_code
                    pdf_path = retry_pdf_path
        elif engine.name == "latexmk":
            return_code, log, pdf_path = _run_latexmk(tex_path, outdir, timeout)
            analysis_log = log
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
            engine=used_engine_name,
            log=str(e),
            diagnostics=[
                Diagnostic(
                    level="error",
                    code="engine-not-found",
                    message=f"LaTeX engine '{used_engine_name}' not found on PATH",
                    raw=str(e),
                )
            ],
        )
    except Exception as e:
        return CompileResult(
            success=False,
            engine=used_engine_name,
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
            engine=used_engine_name,
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
    result_diagnostics.extend(analyse_log(analysis_log or log))

    # Determine success: return code 0 and PDF exists
    success = return_code == 0 and pdf_path.exists()

    if success and not keep_aux:
        _cleanup_auxiliary_files(tex_path, outdir)

    # If compilation failed but we have no error diagnostics, add a generic one.
    if not success and not any(diag.level == "error" for diag in result_diagnostics):
        result_diagnostics.append(
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
        diagnostics=result_diagnostics,
        engine=used_engine_name,
        return_code=return_code,
        workdir=tex_path.parent,
    )
