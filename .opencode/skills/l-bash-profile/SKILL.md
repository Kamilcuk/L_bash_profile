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

## File Creation for ALL Benchmarks (MANDATORY)

**ALWAYS create a markdown report** after running any benchmark. The report must be saved in `doc/` and follow this exact schema based on `PROFILING_WORKFLOW.md`:

```markdown
# [Descriptive Title] Benchmark

## Summary
[Brief summary of findings and which approach is faster]

## Benchmark Results (QEMU instruction count)
| Method/Approach | Instructions | Notes (optional) |
|-----------------|-------------|------------------|
| approach1       | [number]    |                  |
| approach2       | [number]    | [faster/slower note] |

## Full Command Line Used
```bash
# The exact command used to run the benchmark
/path/to/L_bash_profile compare --qemu [options] 'approach1_code' 'approach2_code'
```

## Code Compared (with context - FULLY REPRODUCIBLE)
```bash
# To fully reproduce this benchmark, include ALL executed commands:
# 1. Creation of the setup file in ./temp/
# 2. The actual L_bash_profile compare command

# Example for a benchmark using a setup file:
# mkdir -p ./temp
# cat > ./temp/your_benchmark.sh << 'EOF'
# #!/usr/bin/env bash
# setup() { ... }
# method1() { ... }
# method2() { ... }
# EOF
# chmod +x ./temp/your_benchmark.sh
# 
# /path/to/L_bash_profile compare --qemu --prefix 'source ./temp/your_benchmark.sh; setup "input"' \
#   'method1' 'method2'

# First approach - full function/script as executed (as it appears in the setup file)
# [Include the complete function as it would appear in your setup file]
code snippet for first approach here

# Second approach - full function/script as executed (as it appears in the setup file)  
# [Include the complete function as it would appear in your setup file]
code snippet for second approach here
```

## Intention and Alternative Approaches
[Briefly describe what problem the code is trying to solve]
[Only consider testing alternative approaches if you have a reasonable hypothesis they might be faster based on understanding of Bash internals - do not waste time on brute-force testing of every possible variation]
[If applicable, mention alternative approaches that were considered or tested based on such hypotheses]
[If a better/faster approach was discovered during testing, include it in the results above and explain it here]

## Why [Approach] is Faster
[Explanation of performance differences based on Bash internals]
```

## Common Pitfalls

1. **Don't use `--qemu` for pipelines with external commands** — results only measure bash fork overhead
2. **Don't use `--repeat` with `--qemu`** — QEMU is deterministic; repeat adds redundant overhead
3. **Use `--method TIME --repeat N` for statistical significance** on wall-clock
4. **Profile realistic input sizes** — short strings favor startup overhead; scale to real workloads
5. **Don't rely on `--prefix` for shared state** — use `source` + setup file in `./temp` instead
```

## Quick Reference Commands

| Task | Command |
|------|---------|
| Profile script | `L_bash_profile profile -o trace.txt myscript.sh` |
| Analyze results | `L_bash_profile analyze trace.txt` |
| Compare two snippets | `L_bash_profile compare 'code1' 'code2'` |
| QEMU comparison | `L_bash_profile compare --qemu 'code1' 'code2'` |
| Time-based comparison | `L_bash_profile compare --method TIME --repeat 100 'cmd1' 'cmd2'` |

After running any benchmark, **ALWAYS** create the markdown report in `doc/` with this exact format.
