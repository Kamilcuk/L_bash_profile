---
name: l-bash-profile
description: Profile and compare Bash script performance. Use when you need to identify bottlenecks in Bash scripts, compare execution speed of different implementations, or generate call graphs and instruction counts for Bash code.
---

# L Bash Profile

## Overview

`L_bash_profile` is a powerful tool for deterministic profiling of Bash scripts. It supports multiple profiling methods, including wall-clock time, Linux perf, and high-precision instruction counting via QEMU.

## Quick Start

- **Profile and analyze a command**: `L_bash_profile run 'your_command'`
- **Compare two snippets**: `L_bash_profile compare 'snippet_1' 'snippet_2'`
- **High-precision instruction count**: `L_bash_profile compare --qemu 'snippet_1' 'snippet_2'`

## Profiling Scripts

### Standard Profiling
Use the `run` command to profile a script and see the top longest commands and functions immediately.
```bash
L_bash_profile run './script.sh'
```

### High-Precision (QEMU)
For deterministic results that are not affected by system load, use QEMU instruction counting.
```bash
L_bash_profile run --qemu './script.sh'
```

### Advanced Profiling Workflow
1. **Profile**: `L_bash_profile profile -o trace.txt './script.sh'`
2. **Analyze**: `L_bash_profile analyze trace.txt --top 10`

## Comparing Snippets

Compare the performance of multiple Bash implementations of the same task.

### Using Wall-Clock Time
```bash
L_bash_profile compare 'for i in {1..1000}; do :; done' 'seq 1000 | xargs -I{} :'
```

### Using QEMU Instruction Counts
Deterministic comparison, ideal for micro-benchmarking.
```bash
L_bash_profile compare --qemu '[[ $a == $b ]]' '[ "$a" = "$b" ]'
```

## Analyzing and Visualizing

### Call Graphs
Generate a DOT file of the call graph and visualize it.
```bash
L_bash_profile analyze trace.txt --callgraph graph.dot
xdot graph.dot
```

### Python pstats Compatibility
Convert the trace to `pstats` format for use with tools like `snakeviz`.
```bash
L_bash_profile analyze trace.txt --pstats profile.stats
snakeviz profile.stats
```

## Interpreting Results

- **Instruction Count (QEMU)**: The most stable metric. Lower is better. Represents the number of CPU instructions executed.
- **Top Commands/Functions**: Shows where most of the time (or instructions) is spent. Focus optimization efforts here.
- **Call Graph**: Visualizes the execution flow. Help identify deep nesting or unexpected function calls.
- **Deterministic Profiling**: Unlike wall-clock time, QEMU profiling yields the same results across different runs and systems (assuming the same binary versions), making it perfect for CI/CD performance regression testing.
