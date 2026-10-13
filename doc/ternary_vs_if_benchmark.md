# Arithmetic Ternary vs `if` Statement Benchmark

## Summary

The arithmetic ternary operator inside `(( ))` is consistently faster than an equivalent `if` statement for conditional assignment.

## Benchmark Results (QEMU instruction count)

| Condition | Ternary (insn) | `if` (insn) | Difference |
|-----------|----------------|-------------|------------|
| **TRUE**  (`0 < 1`) | 42,852 | 51,357 | +19.8% slower |
| **FALSE** (`5 < 4`) | 33,962 | 36,812 | +8.4% slower |

## Code Compared

```bash
# Ternary (faster)
(( _L_columns < _L_column + 1 ? _L_columns = _L_column + 1 : 0 ))

# If statement (slower)
if (( _L_columns < _L_column + 1 )); then (( _L_columns = _L_column + 1 )); fi
```

## Why Ternary is Faster

1. **Single arithmetic evaluation context** — The ternary stays entirely inside Bash's built-in arithmetic parser (`(( ))`)
2. **No compound command overhead** — `if/then/fi` requires parsing multiple tokens and executing a compound statement
3. **No branch prediction penalty at shell level** — Both branches are just arithmetic expressions evaluated in-place

## When It Matters

- **Tight loops** running millions of iterations (nanosecond difference per call adds up)
- **Hot paths** in performance-critical Bash code

## When to Prefer `if`

- Readability for complex logic
- Multiple statements in branches
- Non-arithmetic conditions
- General scripting where nanoseconds don't matter

## Methodology

Benchmarked with `L_bash_profile compare --qemu` (deterministic instruction counting via QEMU user-mode emulation). Each snippet run once (QEMU is deterministic).