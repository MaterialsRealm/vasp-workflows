# CLAUDE.md

## Overview

This repository contains VASP (Vienna Ab initio Simulation Package) computational workflows for materials science research. The package provides tools for processing VASP calculations, parsing output files, and building automated workflows for structural optimization, energy calculations, and property analysis.

- Package: `vasp-workflows`
- Language: Python 3.12+
- Core abstraction: `Workdir` (represents a VASP working directory)
- Main use case: Parse and process VASP calculation results

## Setup

### Environment

This project uses `uv` for dependency management:

```bash
uv sync --no-cache --upgrade  # Install all dependencies
source .venv/bin/activate  # Create virtual environment if needed
uv run python  # Run Python
```

### CLI Tool

```bash
vsn --help  # Show available commands
```

## Code Architecture

### Core Pattern: Workdir-Centric Design

The entire codebase revolves around the `Workdir` abstraction:

- `Workdir` (`src/vasp_wfl/workdir.py`): Represents a VASP calculation directory
  - Classifies files (inputs, outputs, temporary)
  - Validates directory completeness with `is_valid()`
  - Thread-safe for parallel processing
  - Immutable representation of a calculation

- Parsers (e.g., `EnergyParser`, `MagnetizationParser`): Extract specific data from OUTCAR/POSCAR
  - Implement `__call__(workdir)` callable protocol
  - Always accept a `Workdir` instance
  - Return parsed data or `None` on failure
  - Static methods for direct file parsing when needed

- Processors: Stateless operations that take `Workdir` instances
  - Replace old subclass-based pattern (deprecated)
  - Implement `WorkdirProcessor` protocol
  - Compose parsers and transformations
  - Support parallel execution via `ThreadPoolExecutor`

### Typical Data Flow

```
Workdir → Parser.__call__() → Structured data (float, dict, array)
          or ProcessorFunc() → Transformed/computed result
```

### Thread Safety

- `Workdir` is immutable and hashable—safe for concurrent use
- Use `ThreadPoolExecutor` with `Workdir` collections for parallel processing
- Parsers and processors must be stateless or thread-safe

Example (from `workdir.py`):

```python
with ThreadPoolExecutor(max_workers=4) as executor:
    results = list(executor.map(parser, workdirs))
```

## Code Standards

### Commit Messages

See `.github/instructions/commit-standards.instructions.md`:

```
<type>[optional scope]: <description>

[optional body]
[optional footer]
```

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `perf`, `chore`, etc.
Description: Imperative mood ("add feature" not "added"), ≤50 chars, no period

### Python Docstrings

See `.github/instructions/python-docstrings.instructions.md`. Key points:

- Imperative mood: "Return the mean" not "Returns the mean"
- One-liners for obvious cases: `"""Return the current working directory."""`
- Multi-line format:

  ```python
  def connect(uri: str, timeout: float | None = None):
      """Open a connection to the server.

      Establishes a TCP connection and performs a handshake.
      Retries are not performed automatically.

      Args:
          uri: Server URI of the form `<scheme>://<host>:<port>`.
          timeout: Optional timeout in seconds.

      Returns:
          A connected Client instance.

      Raises:
          ValueError: If the URI is malformed.
      """
  ```

- Sections: `Args:`, `Returns:`, `Raises:`, `Yields:`
- Identifiers in backticks: `` `timeout`, `open()`, `ValueError` ``

### Type Hints

- Required for public APIs and non-trivial functions
- Use modern syntax: `list[str]` not `List[str]`
- Use `| None` not `Optional[]`

## Key Files

| File | Purpose |
|------|---------|
| `src/vasp_wfl/workdir.py` | Core `Workdir` class and file classification |
| `src/vasp_wfl/energy.py` | Energy parsing from OUTCAR |
| `src/vasp_wfl/magnetization.py` | Magnetic moment parsing |
| `src/vasp_wfl/collinear.py` | Collinear magnetic properties |
| `src/vasp_wfl/cell.py` | Lattice/structure utilities |
| `src/vasp_wfl/force.py` | Force extraction |
| `src/vasp_wfl/poscar.py` | POSCAR parsing and structure info |
| `src/vasp_wfl/spglib.py` | Crystal symmetry analysis |
| `src/vasp_wfl/templating.py` | File templating utilities |

## Common Tasks

### Adding a New Parser

1. Create a class with `@staticmethod` methods in `src/vasp_wfl/newmodule.py`
2. Implement core parsing logic (e.g., `from_file(path)`)
3. Add a `__call__` method that accepts `workdir: Workdir` and calls the core logic
4. Follow docstring standards from `.github/instructions/`
5. Write unit tests in `tests/test_newmodule.py`

### Processing a Directory Tree

```python
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from vasp_wfl import Workdir, EnergyParser

workdirs = [Workdir(d) for d in Path(".").glob("*/")]
with ThreadPoolExecutor(max_workers=4) as executor:
    energies = list(executor.map(EnergyParser(), workdirs))
```

### Debugging a Workdir

```python
workdir = Workdir("/path/to/calc")
print(workdir.is_valid())           # Check if valid VASP directory
print(workdir.path)                 # Path to directory
print(workdir.files)                # All files present
```

## Notes

- Immutability: `Workdir` instances are immutable; create new instances for different paths
- No subclassing: Avoid subclassing `Workdir` or `WorkdirProcessor`; compose instead
- Error handling: Parsers return `None` on failure; check explicitly
- Threading: Use static methods and avoid instance state for thread safety
