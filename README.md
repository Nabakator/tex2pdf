# tex2pdf

A minimalist Python CLI tool for compiling LaTeX files to PDF with structured error reporting. This tool acts as a "core compilation brain" that can be embedded into larger systems (IDEs, web backends, pipelines, etc.).

## Features

- **Multiple engine support**: Works with Tectonic and LaTeXmk
- **Structured error reporting**: Extracts meaningful diagnostics from LaTeX compilation logs
- **Fix recommendations**: Provides actionable suggestions for common LaTeX errors
- **JSON output**: Machine-readable output for programmatic consumption
- **Timeout protection**: Prevents compilation from hanging indefinitely
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

python -m pip install --upgrade pip
python -m pip install .
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

#### Options

- `--outdir`, `-o PATH`: Output directory for generated files (default: `./output`)
- `--engine`, `-e {tectonic,latexmk}`: LaTeX engine to use (default: auto-detect)
- `--json`: Output result as JSON for machine consumption
- `--timeout`, `-t SECONDS`: Maximum compilation time in seconds (default: 120)
- `--help`: Show help message

#### Examples

##### Basic compilation

```bash
# Compile a LaTeX file using the default engine
tex2pdf document.tex

# Compile the example document in the input folder
tex2pdf input/latex_lit_review.tex

# Specify output directory
tex2pdf document.tex --outdir=./output

# Use a specific engine
tex2pdf document.tex --engine=latexmk
```

##### JSON output

```bash
# Get machine-readable output
tex2pdf document.tex --json
```

The JSON output includes:

- `success`: Boolean indicating compilation success
- `pdf_path`: Path to generated PDF (if successful)
- `log`: Full compilation log
- `diagnostics`: Array of diagnostic objects with error codes, messages, and fix recommendations
- `engine`: Engine used for compilation
- `return_code`: Exit code from the LaTeX engine

##### Timeout protection

```bash
# Set a 60-second timeout
tex2pdf document.tex --timeout=60
```

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
    timeout=120
)

if result.success:
    print(f"PDF generated at: {result.pdf_path}")
else:
    print("Compilation failed!")
    for diagnostic in result.diagnostics:
        print(f"{diagnostic.level}: {diagnostic.message}")
```

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
│   └── latex_lit_review.tex # Example input document
├── output/                 # Default output directory
├── src/
│   └── tex2pdf/
│       ├── __init__.py         # Package exports
│       ├── models.py           # Data models (CompileResult, Diagnostic, EngineConfig)
│       ├── analysis.py         # Log analysis with regex-based rule engine
│       ├── core.py             # Core compilation logic
│       └── cli.py              # Typer-based CLI interface
└── tests/
    ├── test_analysis.py    # Tests for log analysis
    └── test_core.py        # Tests for core compilation (with mocking)
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
