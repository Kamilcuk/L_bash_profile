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

## File Creation Guide

### Creating Setup Files for Shared-State Benchmarks

**CRITICAL**: When benchmarking code that depends on shared state (e.g., BASH_REMATCH, globals), **ALWAYS create a setup file** and use `--prefix 'source ./temp/your_script.sh; setup ...'` pattern.

#### Basic Setup File Structure
Create a file in your working directory with these required elements:

1. **Setup function** - initializes shared state
2. **Benchmark functions** - code to be compared
3. **Execution calls** - optional calls to test different scenarios

```bash
#!/usr/bin/env bash
# Your script name here

# Setup function - called first in each benchmark
# Initialize all shared state here
setup() {
    # Your setup logic here (e.g., BASH_REMATCH initialization)
    # Use local variables or global variables as needed
}

# Benchmark function 1
method1() {
    # Your test code here
    # This code runs in the same shell instance as setup()
    # so shared state persists
}

# Benchmark function 2  
method2() {
    # Your test code here
    # This code runs in the same shell instance as setup()
    # so shared state persists
}

# Optional: Test scenarios for quick verification
# (used for edge case testing)
# This runs when the file is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    echo "Testing edge cases..."
    # Run different test scenarios
fi
```

#### Creating a Complete Setup File

```bash
mkdir -p ./temp
cat > ./temp/your_benchmark.sh << 'EOF'
#!/usr/bin/env bash

# Setup function - initializes shared state
setup() {
    local input="$1"
    # Example: regex matching
    [[ "$input" =~ (case1|case2|case3) ]]
    # After this, BASH_REMATCH is set for all benchmark functions
}

# Benchmark 1: Simple if/elif chain
benchmark_method1() {
    if [[ -n ${BASH_REMATCH[1]} ]]; then
        echo "matched case 1"
    elif [[ -n ${BASH_REMATCH[2]} ]]; then
        echo "matched case 2"
    elif [[ -n ${BASH_REMATCH[3]} ]]; then
        echo "matched case 3"
    fi
}

# Benchmark 2: Case with parameter expansion dispatch
benchmark_method2() {
    case "${BASH_REMATCH[1]:+1}${BASH_REMATCH[2]:+2}${BASH_REMATCH[3]:+3}" in
        1) echo "matched 1" ;;
        2) echo "matched 2" ;;
        3) echo "matched 3" ;;
    esac
}

# Test scenarios for verification
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    echo "Testing different match scenarios..."
    setup "test case1"
    benchmark_method1
    _L_json_out=""
    setup "test case2"
    benchmark_method1
    _L_json_out=""
    echo "Edge case testing complete."
fi
EOF

chmod +x ./temp/your_benchmark.sh
```

### Running Benchmarks with Setup Files

#### Using the Setup File
```bash
# Run with different input scenarios
L_bash_profile compare --qemu --prefix 'source ./temp/your_benchmark.sh; setup "test case1"' \
  'benchmark_method1' 'benchmark_method2'

# Test all scenarios
for input in "test case1" "test case2" "test case3"; do
    L_bash_profile compare --qemu --prefix "source ./temp/your_benchmark.sh; setup \"$input\"" \
      'benchmark_method1' 'benchmark_method2'
done
```

#### Best Practices for Setup Files

1. **Keep setup minimal** - setup only sets up what the benchmarks need
2. **Use parameter expansion** - avoid hardcoded values, pass parameters via setup function
3. **Test locally first** - run the setup file directly to verify it works
4. **Document your setup** - comments explaining what each setup value does
5. **Persist state across benchmarks** - ensure both benchmarks run in the same shell instance

### Quick Test for Setup File Creation

```bash
# Create a simple setup file for testing
mkdir -p ./temp
cat > ./temp/test_setup.sh << 'EOF'
#!/usr/bin/env bash
setup() {
    # Simple test: initialize shared state
    shared_var="$1"
    if [[ "$shared_var" == "test" ]]; then
        export SPECIAL_FLAG="enabled"
    else
        export SPECIAL_FLAG="disabled"
    fi
}

test_function() {
    if [[ "$SPECIAL_FLAG" == "enabled" ]]; spread
        echo "Function executed with special flag"
    fi
}

# Local test
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    setup "test"
    test_function
    echo "Local test complete."
fi
EOF

chmod +x ./temp/test_setup.sh
./temp/test_setup.sh
```

## Advanced Topics

### Call Graphs
Generate DOT files for visualization:
```bash
L_bash_profile analyze trace.txt --callgraph graph.dot
xdot graph.dot
```

### Python pstats
Convert to Python profiling format:
```bash
L_bash_profile analyze trace.txt --pstats profile.stats
snakeviz profile.stats
```

## Interpreting Results

- **Instruction Count (QEMU)**: Lower is better. Represents CPU instructions executed.
- **Top Commands/Functions**: Where most time/instructions are spent. Optimize these first.
- **Call Graph**: Visualizes execution flow. Helps identify deep nesting or unexpected calls.
- **Deterministic Profiling**: Same results across runs with same binaries. Perfect for CI/CD.

## Common Mistakes to Avoid

1. **Don't use --qemu for pipelines** - results only measure bash fork overhead
2. **Don't use --repeat with --qemu** - QEMU is deterministic, repeat adds overhead
3. **Always use setup files for shared-state benchmarks** - --prefix with inline code doesn't work
4. **Profile realistic workloads** - short strings favor startup overhead
5. **Don't rely on --prefix for shared state** - use source + setup file pattern

## Quick Reference Commands

| Task | Command |
|------|---------|
| Profile script | `L_bash_profile profile -o trace.txt myscript.sh` |
| Analyze results | `L_bash_profile analyze trace.txt` |
| Compare two snippets | `L_bash_profile compare 'code1' 'code2'` |
| QEMU comparison | `L_bash_profile compare --qemu 'code1' 'code2'` |
| Time-based comparison | `L_bash_profile compare --method TIME --repeat 100 'cmd1' 'cmd2'` |

The skill is designed to help you quickly understand and use L_bash_profile for effective performance profiling and benchmarking of Bash scripts.