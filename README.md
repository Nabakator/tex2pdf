# tex2pdf

A minimalist Python CLI tool for compiling LaTeX files to PDF with structured error reporting. This tool acts as a "core compilation brain" that can be embedded into larger systems (IDEs, web backends, pipelines, etc.).

## Features

- **Multiple engine support**: Works with Tectonic and LaTeXmk
- **Smarter engine auto-selection**: Prefers `latexmk` for `biblatex`/`biber` documents to avoid common version mismatches
- **Standard LaTeX content support**: Compiles documents with images, figures, labels, cross-references, and bibliographies/citations
- **Structured error reporting**: Extracts meaningful diagnostics from LaTeX compilation logs
- **Fix recommendations**: Provides actionable suggestions for common LaTeX errors
- **JSON output**: Machine-readable output for programmatic consumption
- **Timeout protection**: Prevents compilation from hanging indefinitely
- **Aux cleanup by default**: Removes common `.aux`/`.log`/`latexmk` byproducts after successful builds
- **Clean API**: Simple programmatic interface for integration into other tools

## Requirements

### System dependencies

This tool requires one of the following LaTeX engines to be installed and available in your PATH:

- **Tectonic** (preferred): Modern, self-contained LaTeX engine
  - Installation: `cargo install tectonic` or download from [tectonic-typesetting.github.io](https://tectonic-typesetting.github.io/)
  
- **LaTeXmk** (alternative): Traditional LaTeX build tool (requires TeX Live or MiKTeX)
  - Installation: Usually included with TeX Live distributions
  - macOS: `brew install --cask mactex` or `brew install basictex`
  - Linux: `sudo apt-get install texlive-latex-base latexmk`

### Python requirements

- Python 3.10 or higher
- See `requirements.txt` for Python dependencies

## Installation

1. Clone this repository:

   ```bash
   git clone <repository-url>
   cd tex2pdf
   ```

### For users (just run the CLI)

```bash
python3 -m venv .venv

source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

python3 -m pip install --upgrade pip
python3 -m pip install .
```

### For development

```bash
python3 -m venv .venv

source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

python -m pip install -e .

python -m pip install -r requirements-dev.txt
```

**Optional:** Install exactly the pinned runtime dependencies (not needed if you already ran `pip install .`):

```bash
python -m pip install -r requirements.txt
```

## Usage

### CLI

#### Basic syntax

```bash
tex2pdf INPUT_FILE.tex [OPTIONS]
```

Bare filenames are resolved under the `input/` folder by default.

#### Options

- `--outdir`, `-o PATH`: Output directory for generated files (default: `./output`)
- `--engine`, `-e {tectonic,latexmk}`: LaTeX engine to use (default: auto-detect, with `latexmk` preferred for `biblatex` sources)
- `--json`: Output result as JSON for machine consumption
- `--keep-aux`: Keep auxiliary files after a successful compile
- `--timeout`, `-t SECONDS`: Maximum compilation time in seconds (default: 120)
- `--help`: Show help message

#### Examples

##### Basic compilation

```bash
# Compile a LaTeX file using the default engine (from input/)
tex2pdf document.tex

# Compile the example document in the input folder
tex2pdf latex_literature_review.tex

# Specify output directory
tex2pdf document.tex --outdir=./output

# Use a specific engine
tex2pdf document.tex --engine=latexmk

# Keep auxiliary files for debugging
tex2pdf document.tex --keep-aux
```

##### Tutorial: example document

```bash
# 1) Compile the example LaTeX document from input/
tex2pdf latex_literature_review.tex

# 2) Open the result at:
# output/latex_literature_review.pdf
```

The repository intentionally tracks `output/latex_literature_review.pdf` as a demo artifact so the sample output is visible on GitHub without requiring a local compile first.

##### JSON output

```bash
# Get machine-readable output
tex2pdf document.tex --json
```

The JSON output includes:

- `success`: Boolean indicating compilation success
- `pdf_path`: Path to the generated PDF on success, otherwise `null`
- `log`: Full compilation log
- `diagnostics`: Array of diagnostic objects with error codes, messages, and fix recommendations
- `engine`: Engine used for compilation
- `return_code`: Exit code from the LaTeX engine

##### Timeout protection

```bash
# Set a 60-second timeout
tex2pdf document.tex --timeout=60
```

### Supported document features

`tex2pdf` compiles standard LaTeX documents and does not strip document features provided by the underlying TeX engine. In practice, that means the current tool supports:

- Images and figures, for example via `\includegraphics{...}`
- Labels and cross-references such as `\label`, `\ref`, and figure/section references
- Bibliographies and citations, including `biblatex`/`biber` workflows

If you want clickable links inside the generated PDF, add `hyperref` in your LaTeX preamble:

```tex
\usepackage[hidelinks]{hyperref}
```

With that in place, references such as `Figure~\ref{fig:example}` and citations such as `\cite{example2024}` become clickable in the output PDF.

### Programmatic API

You can also use tex2pdf as a Python library:

```python
from pathlib import Path
from tex2pdf import compile_tex, EngineConfig

# Compile a LaTeX file
result = compile_tex(
    tex_path=Path("document.tex"),
    outdir=Path("./output"),
    engine=EngineConfig(name="tectonic"),
    timeout=120,
    keep_aux=False,
)

if result.success:
    print(f"PDF generated at: {result.pdf_path}")
else:
    print("Compilation failed!")
    for diagnostic in result.diagnostics:
        print(f"{diagnostic.level}: {diagnostic.message}")
```

On successful builds, `tex2pdf` removes common auxiliary files such as `.aux`, `.bbl`, `.bcf`, `.blg`, `.fdb_latexmk`, `.fls`, `.log`, `.out`, and `.run.xml`. Failed builds keep them for debugging. Use `--keep-aux` or `keep_aux=True` to preserve them.

## Error handling and diagnostics

The tool provides structured diagnostics for common LaTeX errors:

### Undefined control sequence

Detects undefined LaTeX commands:

```
ERROR [undefined-control-sequence]: Undefined control sequence '\foo'.
Check for typos or missing `\usepackage`/`\newcommand`.
```

### Missing package

Identifies missing `.sty` files:

```
ERROR [missing-package]: Missing package file 'missingpackage.sty'.
Install the appropriate LaTeX package or adjust your preamble.
```

### Runaway argument

Detects unclosed braces or environments:

```
ERROR [runaway-argument]: Runaway argument.
Likely an unclosed brace or environment; check for missing '}' or \end{...} above.
```

### Generic LaTeX errors

Fallback for other LaTeX errors:

```
ERROR [latex-error]: LaTeX reported an error. See raw for details.
```

### Exit codes

- `0`: Compilation succeeded, PDF produced
- `1`: CLI error (invalid arguments, missing file, engine not found)
- `2`: Compilation failed (but CLI behaved correctly)

## Supported error types

The tool currently detects:

- **Undefined control sequences**: Missing commands or packages
- **Missing packages**: `.sty` files not found
- **Runaway arguments**: Unclosed braces or environments
- **Generic LaTeX errors**: Other compilation errors (via `!` markers)

The diagnostic system is extensible - new error patterns can be easily added by extending the rule engine in `tex2pdf/analysis.py`.

## Project structure

```
tex2pdf/
├── pyproject.toml          # Package configuration
├── requirements.txt        # Runtime dependencies
├── requirements-dev.txt    # Development dependencies
├── input/
│   ├── latex_literature_review.tex            # Example input document
│   ├── latex_literature_review_references.bib # Example bibliography
│   └── images/LaTeX_project_logo_bird.png     # Example figure asset
├── output/                 # Default output directory and tracked demo PDF
├── src/
│   └── tex2pdf/
│       ├── __init__.py         # Package exports
│       ├── models.py           # Data models (CompileResult, Diagnostic, EngineConfig)
│       ├── analysis.py         # Log analysis with regex-based rule engine
│       ├── core.py             # Core compilation logic
│       └── cli.py              # Typer-based CLI interface
└── tests/
    ├── test_analysis.py    # Tests for log analysis
    ├── test_cli_integration.py # Real CLI integration tests
    └── test_core.py        # Tests for core compilation logic
```

## Development

### Running tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=tex2pdf

# Run with verbose output
pytest -v
```

The CLI integration tests use the real LaTeX toolchain and are skipped automatically when required system tools such as `latexmk`, `pdflatex`, or `biber` are unavailable.

### Packaging smoke test

```bash
pyproject-build --no-isolation

python -m venv .tmp-release-venv
source .tmp-release-venv/bin/activate
python -m pip install dist/tex2pdf-1.0.0-py3-none-any.whl
tex2pdf latex_literature_review.tex --json
deactivate
```

### Release checklist

Use this checklist before tagging a release:

1. Ensure the worktree is clean aside from the intended version bump and demo PDF update.
2. Run `pytest` and confirm the CLI integration tests are either passing or explicitly skipped for missing system tools.
3. Rebuild the sample review with `tex2pdf latex_literature_review.tex --json` and confirm `output/latex_literature_review.pdf` is current.
4. Run the packaging smoke test in a clean virtual environment.
5. Confirm `pyproject.toml` version/classifiers match the intended release.
6. Review the README examples and JSON contract, then tag the release.

### Extending the diagnostic system

To add support for new error patterns, extend the `LogAnalyzer` class in `tex2pdf/analysis.py`:

```python
def _handle_new_error_type(self, match: re.Match[str]) -> list[Diagnostic]:
    """Handle a new type of LaTeX error."""
    raw = match.group(0)
    return [
        Diagnostic(
            level="error",
            code="new-error-code",
            message="Descriptive message with fix recommendation",
            raw=raw.strip(),
        )
    ]

# Register the rule
analyzer.add_rule(
    re.compile(r"Your error pattern here", re.MULTILINE),
    analyzer._handle_new_error_type,
)
```

### Adding new engines

To add support for a new LaTeX engine:

1. Add a new `_run_engine_name()` function in `tex2pdf/core.py`
2. Update the `compile_tex()` function to handle the new engine
3. Add the engine name to `EngineConfig` type hints

## Limitations

This tool is intentionally minimal and focused on core compilation:

- **Not an editor**: No syntax highlighting or editing features
- **No project management**: Single-file compilation only (no multi-file project support)
- **No watch mode**: Does not monitor files for changes
- **No cloud features**: Local compilation only

This design makes it ideal for embedding into larger systems where these features are provided by the host application.

## License

MIT License

## Contributing

Contributions are welcome! Please ensure:

- All tests pass (`pytest`)
- Code follows type hints and includes docstrings
- New features include appropriate tests
