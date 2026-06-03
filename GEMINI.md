# L_bash_profile

`L_bash_profile` is a command-line tool for profiling Bash scripts, helping identify performance bottlenecks and execution flows.

## Project Overview
- **Purpose**: Deterministic profiling of Bash scripts with support for multiple report formats (top commands/functions, call graphs, `pstats`).
- **Tech Stack**:
  - **Python**: Core logic and analysis (located in `src/L_bash_profile.py`).
  - **Bash**: The target language for profiling; uses `DEBUG` trap or `XTRACE` for capturing execution data.
  - **Libraries**: `click` (CLI), `graphviz` (call graphs), `tabulate` (reports), `pstats` (Python profiling compatibility).

## Building and Running
- **Installation**: Use `uv tool install L_bash_profile` or run directly with `uvx L_bash_profile`.
- **Core Commands**:
  - `profile`: Executes a script and saves the trace (e.g., `L_bash_profile profile -o trace.txt 'myscript.sh'`).
  - `analyze`: Processes a trace file into reports (e.g., `L_bash_profile analyze trace.txt --callstats graph.dot`).
- **Makefile Tasks**:
  - `make test`: Runs `pytest`.
  - `make pyright`: Runs static type checking.
  - `make xdot`: Generates and visualizes call graphs.
  - `make snakeviz`: Visualizes `pstats` output.

## Development Conventions
- **Tooling**: Uses `uv` for dependency management and `basedpyright` for type checking.
- **Testing**: Tests are located in `tests/` and use `pytest`. They often involve running the profiler on sample Bash snippets and verifying the output.
- **Source Structure**:
  - `src/L_bash_profile.py`: Single-file Python implementation for both profiling logic and CLI.
  - `scripts/`: Contains helper Bash scripts (like `bash_profile.sh` which implements the `DEBUG` trap logic) and usage examples.
  - `doc/QEMU_PROFILING.md`: Detailed documentation for the high-precision QEMU profiling architecture.
- **Contribution**: Follow existing patterns in `src/L_bash_profile.py`. Use `click` for new CLI options.
