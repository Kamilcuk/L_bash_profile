# ANSI Escape Sequence Stripping Benchmark

## Summary

Fastest pure-Bash method depends on input length. For typical use cases (short strings, prompts, log lines), the restricted CSI pattern `[0-9;]*[mK]` wins. For very long strings, `sed` becomes competitive.

## Benchmark Results (QEMU instruction count)

### Short string (3 ANSI sequences)
| Method | Instructions | Notes |
|--------|-------------|-------|
| `${s//$'\x1b['[0-9;]*[mK]/}` | **41,942** | Fastest — matches only CSI SGR (m) and EL (K) |
| `${s//$'\x1b['[0-9;]*[a-zA-Z]/}` | 47,294 | Broader CSI match |
| Full extglob `@([@-Z\\-_]|\\[*([0-?])*([ -\\/])[@-~])` | 52,833 | Complete ANSI parser, requires `extglob` |
| `sed 's/\x1b\[[0-9;]*[a-zA-Z]//g'` | 203,166 | Process substitution overhead |

### Medium string (10 ANSI sequences)
| Method | Instructions |
|--------|-------------|
| Full extglob | **107,119** |
| `[0-9;]*[mK]` | 231,181 |
| `[0-9;]*[a-zA-Z]` | 300,210 |

### Long string (20 ANSI sequences)
| Method | Instructions |
|--------|-------------|
| `sed` | **343,859** |
| `[0-9;]*[mK]` | 425,888 |
| `[0-9;]*[a-zA-Z]` | 561,751 |

> **Note:** Full extglob times out on longer strings (catastrophic backtracking on complex pattern).

## Recommended Patterns

```bash
# Fastest for typical use (prompts, log lines, short output)
L_RET=${s//$'\x1b['[0-9;]*[mK]/}

# More complete CSI coverage (slower)
L_RET=${s//$'\x1b['[0-9;]*[a-zA-Z]/}

# Complete ANSI parser (requires extglob, avoid for long strings)
shopt -s extglob
L_RET=${s//$'\x1B'@([@-Z\\-_]|\\[*([0-?])*([ -\\/])[@-~])}

# Best for very long strings / pipelines
L_RET=$(printf "%s" "$s" | sed 's/\x1b\[[0-9;]*[a-zA-Z]//g')
```

## Why `[0-9;]*[mK]` Wins for Short Strings

1. **Minimal backtracking** — Only matches CSI sequences ending in `m` (SGR) or `K` (EL), the two most common in practice
2. **No extglob overhead** — Standard parameter expansion, no extended pattern parsing
3. **Single-pass** — Bash's `${var//pattern/repl}` is optimized for simple glob patterns

## When to Use Each

| Scenario | Recommendation |
|----------|----------------|
| Prompt rendering, status lines | `${s//$'\x1b['[0-9;]*[mK]/}` |
| General terminal output cleaning | `${s//$'\x1b['[0-9;]*[a-zA-Z]/}` |
| Unknown/arbitrary ANSI (osc, dcs, etc) | `sed` or full extglob (short strings only) |
| Processing large logs/files | `sed` (streams, no memory explosion) |

## Methodology

Benchmarked with `L_bash_profile compare --qemu` (deterministic instruction counting). Each test runs the strip operation once on a pre-defined string.