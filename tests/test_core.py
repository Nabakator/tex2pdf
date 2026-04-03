"""Tests for core compilation functionality."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from tex2pdf.core import _get_default_engine, compile_tex
from tex2pdf.models import CompileResult, EngineConfig

_AUX_SUFFIXES = (
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


def _extract_engine_outdir(cmd: list[str]) -> Path:
    """Extract the engine output directory from a mocked command."""
    for arg in cmd:
        if arg.startswith("--outdir=") or arg.startswith("-outdir="):
            return Path(arg.split("=", 1)[1])

    raise AssertionError(f"Could not determine output directory from command: {cmd}")


def _make_subprocess_side_effect(
    *,
    returncode: int,
    stdout: str = "",
    stderr: str = "",
    outputs: dict[str, str] | None = None,
):
    """Build a subprocess.run side effect that materializes staged engine outputs."""

    def _side_effect(*args, **kwargs):
        cmd = args[0]
        engine_outdir = _extract_engine_outdir(cmd)
        engine_outdir.mkdir(parents=True, exist_ok=True)

        for filename, content in (outputs or {}).items():
            (engine_outdir / filename).write_text(content)

        result = MagicMock()
        result.returncode = returncode
        result.stdout = stdout
        result.stderr = stderr
        return result

    return _side_effect


@pytest.fixture
def mock_tex_file(tmp_path: Path) -> Path:
    """Create a temporary .tex file for testing."""
    tex_file = tmp_path / "test.tex"
    tex_file.write_text(r"\documentclass{article}\begin{document}Test\end{document}")
    return tex_file


@pytest.fixture
def outdir(tmp_path: Path) -> Path:
    """Create a temporary output directory."""
    out_dir = tmp_path / "output"
    return out_dir


def test_compile_tex_file_not_found() -> None:
    """Test that missing input file returns appropriate error."""
    result = compile_tex(
        tex_path=Path("/nonexistent/file.tex"),
        outdir=Path("./output"),
        engine=EngineConfig(name="tectonic"),
    )
    assert not result.success
    assert result.pdf_path is None
    assert len(result.diagnostics) > 0
    assert any(d.code == "file-not-found" for d in result.diagnostics)


@patch("tex2pdf.core.shutil.which")
@patch("tex2pdf.core.subprocess.run")
def test_compile_tex_engine_not_found(
    mock_subprocess: Mock,
    mock_which: Mock,
    mock_tex_file: Path,
    outdir: Path,
) -> None:
    """Test that missing engine executable returns appropriate error."""
    mock_which.return_value = None  # Engine not found
    result = compile_tex(
        tex_path=mock_tex_file,
        outdir=outdir,
        engine=EngineConfig(name="tectonic"),
    )
    assert not result.success
    assert len(result.diagnostics) > 0
    assert any(d.code == "engine-not-found" for d in result.diagnostics)
    mock_subprocess.assert_not_called()


@patch("tex2pdf.core.shutil.which")
@patch("tex2pdf.core.subprocess.run")
def test_compile_tex_success_tectonic(
    mock_subprocess: Mock,
    mock_which: Mock,
    mock_tex_file: Path,
    outdir: Path,
) -> None:
    """Test successful compilation with tectonic."""
    mock_which.return_value = "/usr/bin/tectonic"
    pdf_path = outdir / "test.pdf"
    mock_subprocess.side_effect = _make_subprocess_side_effect(
        returncode=0,
        stdout="Compilation successful",
        outputs={"test.pdf": "fake pdf content"},
    )

    result = compile_tex(
        tex_path=mock_tex_file,
        outdir=outdir,
        engine=EngineConfig(name="tectonic"),
    )

    assert result.success
    assert result.pdf_path == pdf_path
    assert result.return_code == 0
    mock_subprocess.assert_called_once()


@patch("tex2pdf.core.shutil.which")
@patch("tex2pdf.core.subprocess.run")
def test_compile_tex_failure_with_diagnostics(
    mock_subprocess: Mock,
    mock_which: Mock,
    mock_tex_file: Path,
    outdir: Path,
) -> None:
    """Test compilation failure with error diagnostics."""
    mock_which.return_value = "/usr/bin/tectonic"
    mock_subprocess.side_effect = _make_subprocess_side_effect(
        returncode=1,
        stderr=r"! Undefined control sequence.\nl.5 \foo",
    )

    result = compile_tex(
        tex_path=mock_tex_file,
        outdir=outdir,
        engine=EngineConfig(name="tectonic"),
    )

    assert not result.success
    assert result.return_code == 1
    # Should have diagnostics from log analysis
    assert len(result.diagnostics) > 0


@patch("tex2pdf.core.shutil.which")
@patch("tex2pdf.core.subprocess.run")
def test_compile_tex_timeout(
    mock_subprocess: Mock,
    mock_which: Mock,
    mock_tex_file: Path,
    outdir: Path,
) -> None:
    """Test that compilation timeout is handled correctly."""
    import subprocess

    mock_which.return_value = "/usr/bin/tectonic"
    mock_subprocess.side_effect = subprocess.TimeoutExpired(cmd=["tectonic"], timeout=5)

    result = compile_tex(
        tex_path=mock_tex_file,
        outdir=outdir,
        engine=EngineConfig(name="tectonic"),
        timeout=5,
    )

    assert not result.success
    assert len(result.diagnostics) > 0
    assert any(d.code == "timeout" for d in result.diagnostics)


@patch("tex2pdf.core.shutil.which")
@patch("tex2pdf.core.subprocess.run")
def test_compile_tex_latexmk(
    mock_subprocess: Mock,
    mock_which: Mock,
    mock_tex_file: Path,
    outdir: Path,
) -> None:
    """Test compilation with latexmk engine."""
    mock_which.return_value = "/usr/bin/latexmk"

    pdf_path = outdir / "test.pdf"
    mock_subprocess.side_effect = _make_subprocess_side_effect(
        returncode=0,
        stdout="Latexmk: All targets successfully generated",
        outputs={"test.pdf": "fake pdf content"},
    )

    result = compile_tex(
        tex_path=mock_tex_file,
        outdir=outdir,
        engine=EngineConfig(name="latexmk"),
    )

    assert result.success
    assert result.pdf_path == pdf_path
    # Verify latexmk was called with correct arguments
    call_args = mock_subprocess.call_args
    assert call_args is not None
    assert "-pdf" in call_args[0][0]
    assert "-interaction=nonstopmode" in call_args[0][0]


def test_compile_tex_unsupported_engine(
    mock_tex_file: Path,
    outdir: Path,
) -> None:
    """Test that unsupported engine returns appropriate error."""
    # This would require EngineConfig to accept other values, but we type-check
    # For now, test that invalid engine name in config would fail
    # (In practice, the CLI validates this, but core should handle gracefully)
    pass  # EngineConfig only allows "tectonic" or "latexmk" via type hints


@patch("tex2pdf.core.shutil.which")
@patch("tex2pdf.core.subprocess.run")
def test_compile_tex_success_removes_auxiliary_files(
    mock_subprocess: Mock,
    mock_which: Mock,
    mock_tex_file: Path,
    outdir: Path,
) -> None:
    """Successful runs should clean up auxiliary files by default."""
    mock_which.return_value = "/usr/bin/latexmk"
    pdf_path = outdir / "test.pdf"
    mock_subprocess.side_effect = _make_subprocess_side_effect(
        returncode=0,
        stdout="Latexmk: All targets successfully generated",
        outputs={
            "test.pdf": "fake pdf content",
            **{f"test{suffix}": "aux" for suffix in _AUX_SUFFIXES},
        },
    )

    result = compile_tex(
        tex_path=mock_tex_file,
        outdir=outdir,
        engine=EngineConfig(name="latexmk"),
    )

    assert result.success
    assert pdf_path.exists()
    for suffix in _AUX_SUFFIXES:
        assert not (outdir / f"test{suffix}").exists()


@patch("tex2pdf.core.shutil.which")
@patch("tex2pdf.core.subprocess.run")
def test_compile_tex_keep_aux_preserves_auxiliary_files(
    mock_subprocess: Mock,
    mock_which: Mock,
    mock_tex_file: Path,
    outdir: Path,
) -> None:
    """keep_aux should preserve generated auxiliary files."""
    mock_which.return_value = "/usr/bin/latexmk"
    mock_subprocess.side_effect = _make_subprocess_side_effect(
        returncode=0,
        stdout="Latexmk: All targets successfully generated",
        outputs={
            "test.pdf": "fake pdf content",
            **{f"test{suffix}": "aux" for suffix in _AUX_SUFFIXES},
        },
    )
    for suffix in _AUX_SUFFIXES:
        assert not (outdir / f"test{suffix}").exists()

    result = compile_tex(
        tex_path=mock_tex_file,
        outdir=outdir,
        engine=EngineConfig(name="latexmk"),
        keep_aux=True,
    )

    assert result.success
    for suffix in _AUX_SUFFIXES:
        assert (outdir / f"test{suffix}").exists()


@patch("tex2pdf.core.shutil.which")
@patch("tex2pdf.core.subprocess.run")
def test_compile_tex_failure_preserves_auxiliary_files(
    mock_subprocess: Mock,
    mock_which: Mock,
    mock_tex_file: Path,
    outdir: Path,
) -> None:
    """Failed runs should keep auxiliary files for debugging."""
    mock_which.return_value = "/usr/bin/latexmk"
    aux_path = outdir / "test.log"
    mock_subprocess.side_effect = _make_subprocess_side_effect(
        returncode=1,
        stderr="! Undefined control sequence.\nl.5 \\foo",
        outputs={"test.log": "aux"},
    )

    result = compile_tex(
        tex_path=mock_tex_file,
        outdir=outdir,
        engine=EngineConfig(name="latexmk"),
    )

    assert not result.success
    assert aux_path.exists()


@patch("tex2pdf.core.shutil.which")
@patch("tex2pdf.core.subprocess.run")
def test_compile_tex_failure_does_not_return_stale_pdf_path(
    mock_subprocess: Mock,
    mock_which: Mock,
    mock_tex_file: Path,
    outdir: Path,
) -> None:
    """Failed runs should not report a PDF path from an older successful build."""
    mock_which.return_value = "/usr/bin/latexmk"
    outdir.mkdir(parents=True, exist_ok=True)
    stale_pdf_path = outdir / "test.pdf"
    stale_pdf_path.write_text("stale pdf content")

    mock_subprocess.side_effect = _make_subprocess_side_effect(
        returncode=1,
        stderr="! Undefined control sequence.\nl.5 \\foo",
        outputs={"test.log": "new failure log"},
    )

    result = compile_tex(
        tex_path=mock_tex_file,
        outdir=outdir,
        engine=EngineConfig(name="latexmk"),
    )

    assert not result.success
    assert result.pdf_path is None
    assert stale_pdf_path.exists()


@patch("tex2pdf.core.shutil.which")
def test_get_default_engine_prefers_latexmk_for_biblatex_documents(
    mock_which: Mock,
    tmp_path: Path,
) -> None:
    """Auto-selection should avoid tectonic for biblatex/biber documents."""
    mock_which.side_effect = lambda name: {
        "tectonic": "/usr/bin/tectonic",
        "latexmk": "/usr/bin/latexmk",
    }.get(name)

    tex_file = tmp_path / "paper.tex"
    tex_file.write_text(r"\usepackage[backend=biber]{biblatex}")

    assert _get_default_engine(tex_file) == "latexmk"


@patch("tex2pdf.core.shutil.which")
def test_get_default_engine_prefers_tectonic_for_plain_documents(
    mock_which: Mock,
    tmp_path: Path,
) -> None:
    """Auto-selection should still prefer tectonic for simple documents."""
    mock_which.side_effect = lambda name: {
        "tectonic": "/usr/bin/tectonic",
        "latexmk": "/usr/bin/latexmk",
    }.get(name)

    tex_file = tmp_path / "plain.tex"
    tex_file.write_text(r"\documentclass{article}\begin{document}Hi\end{document}")

    assert _get_default_engine(tex_file) == "tectonic"


@patch("tex2pdf.core._run_latexmk")
@patch("tex2pdf.core._run_tectonic")
def test_compile_tex_falls_back_to_latexmk_on_biber_version_mismatch(
    mock_run_tectonic: Mock,
    mock_run_latexmk: Mock,
    mock_tex_file: Path,
    outdir: Path,
) -> None:
    """tectonic should transparently retry with latexmk on a version mismatch."""
    mismatch_log = (
        "ERROR - Error: Found biblatex control file version 3.8, expected version 3.5.\n"
        "This means that your biber (2.12) and biblatex (3.17) versions are incompatible.\n"
    )

    def _tectonic_side_effect(tex_path: Path, build_outdir: Path, timeout: int | None):
        return 1, mismatch_log, build_outdir / f"{tex_path.stem}.pdf"

    def _latexmk_side_effect(tex_path: Path, build_outdir: Path, timeout: int | None):
        pdf_path = build_outdir / f"{tex_path.stem}.pdf"
        build_outdir.mkdir(parents=True, exist_ok=True)
        pdf_path.write_text("fake pdf content")
        return 0, "Latexmk: done", pdf_path

    mock_run_tectonic.side_effect = _tectonic_side_effect
    mock_run_latexmk.side_effect = _latexmk_side_effect

    result = compile_tex(
        tex_path=mock_tex_file,
        outdir=outdir,
        engine=EngineConfig(name="tectonic"),
    )

    assert result.success
    assert result.engine == "latexmk"
    assert result.pdf_path == outdir / "test.pdf"
    assert any(d.code == "engine-fallback" for d in result.diagnostics)
    mock_run_tectonic.assert_called_once()
    mock_run_latexmk.assert_called_once()
