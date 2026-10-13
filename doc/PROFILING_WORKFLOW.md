# L_bash_profile Profiling Workflow

## Understanding QEMU Profiling

### What QEMU Actually Measures

`L_bash_profile compare --qemu` / `profile --qemu` uses:
```
qemu-x86_64 -one-insn-per-tb -d exec,strace -D <fifo> bash -c '<script>'
```

**QEMU only traces the main `bash` process** — instruction count covers:
- Bash interpreter startup
- Builtin command execution (arithmetic, parameter expansion, etc.)
- `fork()` / `pipe()` / `wait()` syscall overhead for pipelines

**QEMU does NOT count instructions in:**
- External processes (`perl`, `sed`, `python3`, `awk`, etc.)
- Child bash processes in subshells `$(...)` or pipelines
- Any forked process

### When QEMU Results Are Misleading

| Scenario | QEMU Result | Reality |
|----------|-------------|---------|
| `a=$((a+1))` vs `((++a))` | ✅ Accurate | Pure bash builtins |
| `perl -pe '...'` vs `sed '...'` | ❌ Meaningless | Both show only `fork+pipe+wait` |
| `bash -c '...'` subshell | ❌ Partial | Only parent bash traced |

### Correct Profiling Methods by Use Case

| Target | Method | Command |
|--------|--------|---------|
| Pure bash builtins / arithmetic | `--qemu` | `L_bash_profile compare --qemu '((++a))' 'a=$((a+1))'` |
| External command pipelines | `--method TIME` | `L_bash_profile compare --method TIME --repeat 100 'cmd1 \| cmd2'` |
| Full system (kernel + userspace) | `--method PERF` | `L_bash_profile compare --perf 'cmd'` |
| Instruction count including children | Not supported | Use `perf stat -e instructions bash -c '...'` |

## Correct Benchmarking Methodology

### The Shared State Problem

When benchmarking code that depends on state set by a prefix (e.g., `BASH_REMATCH` from a regex match), **the prefix must run in the same shell instance as the measured code**. Using `--prefix` with inline code fails because the regex runs in the prefix shell but `BASH_REMATCH` doesn't persist to the measured snippet (each snippet runs in a fresh `bash -c`).

### Complete Setup Script Example

Create and run:

```bash
mkdir -p ./temp
cat > ./temp/bench_regex.sh << 'EOF'
#!/usr/bin/env bash
# ./temp/bench_regex.sh - Setup and methods for regex dispatch benchmark

# Setup function: initializes shared state (BASH_REMATCH)
setup_regex() {
    local a="$1"
    [[ $a =~ (long)|(regex)|(here)|(with)|(cases) ]]
}

# Method 1: if/elif chain
case_if_elif() {
    if [[ -n ${BASH_REMATCH[1]} ]]; then :; 
    elif [[ -n ${BASH_REMATCH[2]} ]]; then :; 
    elif [[ -n ${BASH_REMATCH[3]} ]]; then :; 
    elif [[ -n ${BASH_REMATCH[4]} ]]; then :; 
    elif [[ -n ${BASH_REMATCH[5]} ]]; then :; fi
}

# Method 2: case with parameter expansion dispatch
case_case() {
    case "${BASH_REMATCH[1]:+1}${BASH_REMATCH[2]:+2}${BASH_REMATCH[3]:+3}${BASH_REMATCH[4]:+4}${BASH_REMATCH[5]:+5}" in
        1) :;; 2) :;; 3) :;; 4) :;; 5) :;; esac
}
EOF

# Benchmark each match position
for m in long regex here with cases nomatch; do
    L_bash_profile compare --qemu \
        --prefix "source ./temp/bench_regex.sh; setup_regex \"$m\"" \
        'case_if_elif' 'case_case'
done
```

### Anti-Patterns to Avoid

```bash
# ❌ WRONG: BASH_REMATCH doesn't persist from prefix to snippet
L_bash_profile compare --qemu --prefix 'a="x"; [[ $a =~ (pat) ]]' \
  'if [[ -n ${BASH_REMATCH[1]} ]]; then ...' \
  'case ...'

# ❌ WRONG: Subshell loses state
L_bash_profile compare --qemu --prefix 'a="x"; [[ $a =~ (pat) ]]' \
  '$(if [[ -n ${BASH_REMATCH[1]} ]]; then ...)' \
  '$(case ...)'
```

## Recommended Workflow

### 1. Quick Microbenchmarks (pure bash)
```bash
# Arithmetic, parameter expansion, builtins
L_bash_profile compare --qemu '((++a))' 'a=$((a+1))'
```

### 2. Shared-State Benchmarks (regex, arrays, globals)
```bash
# Create setup file once
mkdir -p ./temp
cat > ./temp/bench.sh << 'EOF'
setup() { ... }
method1() { ... }
method2() { ... }
EOF

# Benchmark with shared state
L_bash_profile compare --qemu --prefix 'source ./temp/bench.sh; setup "input"' \
  'method1' 'method2'
```

### 3. Pipeline / External Command Benchmarks
```bash
# Use wall-clock time with multiple repeats
L_bash_profile compare --method TIME --repeat 100 \
  'printf "%s" "$s" | perl -pe "..."' \
  'printf "%s" "$s" | sed -E "..."'
```

### 4. Full System Profiling
```bash
# Linux perf (requires root/perf_event_paranoid)
L_bash_profile compare --perf 'bash -c "..."'
```

### 5. Script Profiling (not comparison)
```bash
# Profile a script file
L_bash_profile profile --qemu -o trace.txt myscript.sh
L_bash_profile analyze trace.txt
```

### 6. Saving Benchmark Results
After running benchmarks or profiling, save the results as a markdown file in the `doc/` directory following this schema:
```markdown
# [Descriptive Title] Benchmark

## Summary
[Brief summary of findings and which approach is faster]

## Benchmark Results (QEMU instruction count)
| Method/Approach | Instructions | Notes (optional) |
|-----------------|-------------|------------------|
| approach1       | 100000      |                  |
| approach2       | 90000       | -10% faster      |

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
