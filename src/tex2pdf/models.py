"""Data models for tex2pdf compilation results and diagnostics."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional


@dataclass
class Diagnostic:
    """A diagnostic message extracted from LaTeX compilation logs."""

    level: Literal["error", "warning", "info"]
    code: str
    message: str
    raw: str
    file: Optional[str] = None
    line: Optional[int] = None

    def to_dict(self) -> dict:
        """Convert diagnostic to a dictionary for JSON serialization."""
        return {
            "level": self.level,
            "code": self.code,
            "message": self.message,
            "raw": self.raw,
            "file": self.file,
            "line": self.line,
        }


@dataclass
class EngineConfig:
    """Configuration for a LaTeX engine."""

    name: Literal["tectonic", "latexmk"]


@dataclass
class CompileResult:
    """Result of a LaTeX compilation attempt."""

    success: bool
    pdf_path: Optional[Path] = None
    log: str = ""
    diagnostics: list[Diagnostic] = field(default_factory=list)
    engine: str = ""
    return_code: Optional[int] = None
    workdir: Optional[Path] = None

    def to_dict(self) -> dict:
        """Convert result to a dictionary for JSON serialization."""
        return {
            "success": self.success,
            "pdf_path": str(self.pdf_path) if self.pdf_path else None,
            "log": self.log,
            "diagnostics": [d.to_dict() for d in self.diagnostics],
            "engine": self.engine,
            "return_code": self.return_code,
            "workdir": str(self.workdir) if self.workdir else None,
        }
