"""CLI interface for tex2pdf."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from typing import Annotated

import typer

from tex2pdf.core import compile_tex, _get_default_engine
from tex2pdf.models import CompileResult, Diagnostic, EngineConfig

app = typer.Typer(
    name="tex2pdf",
    help="Compile LaTeX files to PDF with structured error reporting",
)


def _print_diagnostics(result: CompileResult) -> None:
    """Print diagnostics in human-readable format."""
    if not result.diagnostics:
        return

    for diag in result.diagnostics:
        level_marker = {
            "error": "ERROR",
            "warning": "WARNING",
            "info": "INFO",
        }.get(diag.level, "INFO")
        typer.echo(
            f"{level_marker} [{diag.code}]: {diag.message}",
            err=True,
        )
        typer.echo(f"  ↳ raw: {diag.raw[:200]}...", err=True)


@app.command()
def main(
    input_file: Annotated[
        Path,
        typer.Argument(help="Path to the input .tex file"),
    ],
    outdir: Annotated[
        Path,
        typer.Option("--outdir", "-o", help="Output directory for generated files"),
    ] = Path("./output"),
    engine: Annotated[
        str,
        typer.Option("--engine", "-e", help="LaTeX engine to use (tectonic or latexmk)"),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output result as JSON"),
    ] = False,
    timeout: Annotated[
        int,
        typer.Option("--timeout", "-t", help="Maximum compilation time in seconds"),
    ] = 120,
) -> None:
    """Compile a LaTeX file to PDF.

    Examples:
        tex2pdf document.tex
        tex2pdf document.tex --outdir=./output --engine=latexmk
        tex2pdf document.tex --json
    """
    # Resolve input file path
    tex_path = input_file.resolve()
    if not tex_path.exists():
        error_msg = f"Error: Input file not found: {tex_path}"
        if json_output:
            result = CompileResult(
                success=False,
                diagnostics=[
                    Diagnostic(
                        level="error",
                        code="file-not-found",
                        message=error_msg,
                        raw=str(tex_path),
                    )
                ],
            )
            typer.echo(json.dumps(result.to_dict(), indent=2))
        else:
            typer.echo(error_msg, err=True)
        sys.exit(1)

    # Determine engine
    if engine is None:
        engine_name = _get_default_engine()
    else:
        engine_name = engine.lower()

    if engine_name not in ("tectonic", "latexmk"):
        error_msg = f"Error: Invalid engine '{engine_name}'. Must be 'tectonic' or 'latexmk'."
        if json_output:
            result = CompileResult(
                success=False,
                diagnostics=[
                    Diagnostic(
                        level="error",
                        code="invalid-engine",
                        message=error_msg,
                        raw=engine_name,
                    )
                ],
            )
            typer.echo(json.dumps(result.to_dict(), indent=2))
        else:
            typer.echo(error_msg, err=True)
        sys.exit(1)

    engine_config = EngineConfig(name=engine_name)

    # Compile
    result = compile_tex(
        tex_path=tex_path,
        outdir=outdir.resolve(),
        engine=engine_config,
        timeout=timeout,
    )

    # Handle JSON output
    if json_output:
        typer.echo(json.dumps(result.to_dict(), indent=2))
        sys.exit(0 if result.success else 2)

    # Human-readable output
    if result.success and result.pdf_path:
        typer.echo(f"OK: {result.pdf_path.resolve()}")
        sys.exit(0)
    else:
        typer.echo("Compilation failed.", err=True)
        _print_diagnostics(result)
        sys.exit(2)


if __name__ == "__main__":
    app()
