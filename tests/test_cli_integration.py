"""End-to-end CLI integration tests."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPO_ROOT / "src"
SAMPLE_TEX = REPO_ROOT / "input" / "latex_literature_review.tex"
SAMPLE_BIB = REPO_ROOT / "input" / "latex_literature_review_references.bib"
SAMPLE_IMAGE = REPO_ROOT / "input" / "images" / "LaTeX_project_logo_bird.png"
SUCCESS_AUX_SUFFIXES = (
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


def _has_command(name: str) -> bool:
    return shutil.which(name) is not None


def _run_cli(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        f"{SOURCE_ROOT}{os.pathsep}{existing_pythonpath}"
        if existing_pythonpath
        else str(SOURCE_ROOT)
    )
    return subprocess.run(
        [sys.executable, "-m", "tex2pdf.cli", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        env=env,
    )


@pytest.mark.skipif(
    not all(_has_command(name) for name in ("latexmk", "pdflatex", "biber")),
    reason="CLI integration test requires latexmk, pdflatex, and biber",
)
def test_cli_compiles_sample_review_end_to_end(tmp_path: Path) -> None:
    """The sample review should compile successfully through the public CLI."""
    sample_dir = tmp_path / "sample"
    image_dir = sample_dir / "images"
    image_dir.mkdir(parents=True)
    shutil.copy2(SAMPLE_TEX, sample_dir / SAMPLE_TEX.name)
    shutil.copy2(SAMPLE_BIB, sample_dir / SAMPLE_BIB.name)
    shutil.copy2(SAMPLE_IMAGE, image_dir / SAMPLE_IMAGE.name)

    outdir = tmp_path / "output"
    result = _run_cli(
        str(sample_dir / SAMPLE_TEX.name),
        "--json",
        "--outdir",
        str(outdir),
        cwd=REPO_ROOT,
    )

    assert result.returncode == 0, result.stderr or result.stdout

    payload = json.loads(result.stdout)
    pdf_path = outdir / "latex_literature_review.pdf"

    assert payload["success"] is True
    assert payload["engine"] == "latexmk"
    assert payload["pdf_path"] == str(pdf_path)
    assert pdf_path.exists()
    for suffix in SUCCESS_AUX_SUFFIXES:
        assert not (outdir / f"latex_literature_review{suffix}").exists()


@pytest.mark.skipif(
    not all(_has_command(name) for name in ("latexmk", "pdflatex")),
    reason="CLI integration test requires latexmk and pdflatex",
)
def test_cli_failure_returns_null_pdf_path_with_stale_output_present(tmp_path: Path) -> None:
    """A failed CLI run should not report a stale PDF path from a previous build."""
    tex_path = tmp_path / "broken.tex"
    tex_path.write_text(
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        "\\undefinedcommand\n"
        "\\end{document}\n"
    )

    outdir = tmp_path / "output"
    outdir.mkdir()
    stale_pdf = outdir / "broken.pdf"
    stale_pdf.write_text("stale pdf content")

    result = _run_cli(
        str(tex_path),
        "--json",
        "--engine",
        "latexmk",
        "--outdir",
        str(outdir),
        cwd=REPO_ROOT,
    )

    assert result.returncode == 2, result.stderr or result.stdout

    payload = json.loads(result.stdout)

    assert payload["success"] is False
    assert payload["pdf_path"] is None
    assert stale_pdf.exists()

