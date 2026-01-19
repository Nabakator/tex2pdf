"""Log analysis and diagnostic extraction from LaTeX compilation logs."""

from __future__ import annotations

import re
from typing import Callable

from tex2pdf.models import Diagnostic

# Type alias for a rule handler function
RuleHandler = Callable[[re.Match[str]], list[Diagnostic]]


class LogAnalyzer:
    """Analyzes LaTeX compilation logs to extract diagnostics."""

    def __init__(self) -> None:
        """Initialize the analyzer with default rules."""
        self.rules: list[tuple[re.Pattern[str], RuleHandler]] = []
        self._register_default_rules()

    def _register_default_rules(self) -> None:
        """Register the default diagnostic rules."""
        # Undefined control sequence - more robust pattern
        self.add_rule(
            re.compile(
                r"Undefined control sequence[^\n]*\nl\.\d+\s+(\\[a-zA-Z@]+[a-zA-Z0-9@]*)",
                re.MULTILINE,
            ),
            self._handle_undefined_control_sequence,
        )

        # Missing package file
        self.add_rule(
            re.compile(
                r"LaTeX Error: File `([^']+\.sty)' not found",
                re.MULTILINE,
            ),
            self._handle_missing_package,
        )

        # Runaway argument
        self.add_rule(
            re.compile(r"Runaway argument\??", re.MULTILINE),
            self._handle_runaway_argument,
        )

        # Generic LaTeX error lines (starting with !)
        self.add_rule(
            re.compile(r"^!(.*)$", re.MULTILINE),
            self._handle_generic_error,
        )

    def add_rule(self, pattern: re.Pattern[str], handler: RuleHandler) -> None:
        """Add a new analysis rule.

        Args:
            pattern: Regex pattern to match in the log
            handler: Function that takes a match and returns a list of Diagnostic objects
        """
        self.rules.append((pattern, handler))

    def _handle_undefined_control_sequence(self, match: re.Match[str]) -> list[Diagnostic]:
        """Handle undefined control sequence errors."""
        raw = match.group(0)
        sequence = match.group(1) if match.groups() else "unknown"
        # Remove leading backslash if present (it's in the match already)
        if sequence.startswith("\\"):
            sequence_name = sequence
        else:
            sequence_name = f"\\{sequence}"
        return [
            Diagnostic(
                level="error",
                code="undefined-control-sequence",
                message=(
                    f"Undefined control sequence '{sequence_name}'. "
                    "Check for typos or missing `\\usepackage`/`\\newcommand`."
                ),
                raw=raw.strip(),
            )
        ]

    def _handle_missing_package(self, match: re.Match[str]) -> list[Diagnostic]:
        """Handle missing package file errors."""
        package = match.group(1)
        raw = match.group(0)
        return [
            Diagnostic(
                level="error",
                code="missing-package",
                message=(
                    f"Missing package file '{package}'. "
                    "Install the appropriate LaTeX package or adjust your preamble."
                ),
                raw=raw.strip(),
            )
        ]

    def _handle_runaway_argument(self, match: re.Match[str]) -> list[Diagnostic]:
        """Handle runaway argument errors."""
        raw = match.group(0)
        return [
            Diagnostic(
                level="error",
                code="runaway-argument",
                message=(
                    "Runaway argument. Likely an unclosed brace or environment; "
                    "check for missing '}' or \\end{...} above."
                ),
                raw=raw.strip(),
            )
        ]

    def _handle_generic_error(self, match: re.Match[str]) -> list[Diagnostic]:
        """Handle generic LaTeX error lines."""
        error_text = match.group(1).strip()
        raw = match.group(0).strip()

        # Skip if this is already matched by a more specific rule
        if any(
            code in raw.lower()
            for code in [
                "undefined control sequence",
                "file",
                "not found",
                "runaway argument",
            ]
        ):
            return []

        return [
            Diagnostic(
                level="error",
                code="latex-error",
                message="LaTeX reported an error. See raw for details.",
                raw=raw,
            )
        ]

    def analyse(self, log: str) -> list[Diagnostic]:
        """Analyze a LaTeX compilation log and extract diagnostics.

        Args:
            log: The full compilation log text

        Returns:
            A list of Diagnostic objects extracted from the log
        """
        diagnostics: list[Diagnostic] = []
        matched_positions: set[tuple[int, int]] = set()

        for pattern, handler in self.rules:
            for match in pattern.finditer(log):
                # Avoid duplicate diagnostics from overlapping matches
                match_span = match.span()
                if match_span in matched_positions:
                    continue

                try:
                    new_diagnostics = handler(match)
                    diagnostics.extend(new_diagnostics)
                    matched_positions.add(match_span)
                except Exception:
                    # If a handler fails, continue with other rules
                    continue

        return diagnostics


# Global analyzer instance
_analyzer = LogAnalyzer()


def analyse_log(log: str) -> list[Diagnostic]:
    """Analyze a LaTeX compilation log and extract diagnostics.

    This is the main entry point for log analysis.

    Args:
        log: The full compilation log text

    Returns:
        A list of Diagnostic objects extracted from the log
    """
    return _analyzer.analyse(log)
