# Conditional Append Profile

## Profile Summary
Benchmark comparing three approaches for conditionally appending newline+indent to `_L_json_out`. **method2 (ternary parameter expansion)** is fastest overall (54643 instructions) for the set/match case.

## Benchmark Results (QEMU instruction count)
| Case / Method | Instructions | Notes |
|---------------|-------------|-------|
| set / match — method1 (compound) | 56189 | baseline |
| set / match — method2 (ternary) | 54643 | -1546 (-2.7% faster) |
| set / match — method3 (arithmetic) | 57682 | +3039 (+5.4% slower) |
| set / nomatch — method1 | 45728 | baseline |
| set / nomatch — method2 | 36740 | -8988 faster |
| set / nomatch — method3 | 47699 | +10959 slower |
| empty / match — method1 | 38661 | baseline |
| empty / match — method2 | 45044 | +6383 slower |
| empty / match — method3 | 37573 | -7471 faster |
| empty / nomatch — method1 | 38784 | baseline |
| empty / nomatch — method2 | 36740 | -2044 faster |
| empty / nomatch — method3 | 37707 | +967 slower |

## How It Was Profiled
Method: `L_bash_profile compare --qemu --prefix 'source ./temp/bench_conditional_append.sh; setup "set" "match"' 'method1' 'method2' 'method3'`
Setup file: `./temp/bench_conditional_append.sh`
Approach: Pure bash builtins with shared-state setup script (methodology from PROFILING_WORKFLOW.md)

## Full Command Line Used
```bash
L_bash_profile compare --qemu --prefix 'source ./temp/bench_conditional_append.sh; setup "set" "match"' 'method1' 'method2' 'method3'
```

## Code Compared (FULLY REPRODUCIBLE — full source of setup file)
```bash
#!/usr/bin/env bash
setup() {
    local wide_state="$1" last_state="$2"
    case "$wide_state" in
        "set") _L_wide="1" ;;
        "empty") _L_wide="" ;;
    esac
    case "$last_state" in
        "match") _L_last="a" ;;
        "nomatch") _L_last="b" ;;
    esac
    _L_json_out=""
    indent="    "
}
method1() {
    if [[ -n "$_L_wide" && "$_L_last" == "a" ]]; then
        _L_json_out+=$'\n'"$indent"
    fi
}
method2() {
    if [[ "$_L_last" == "a" ]]; then
        _L_json_out+=${_L_wide:+$'\n'"$indent"}
    fi
}
method3() {
    if (( _L_wide )) && [[ "$_L_last" == "a" ]]; then
        _L_json_out+=$'\n'"$indent"
    fi
}
```

## Intention and Alternative Approaches
Compare three Bash approaches for conditional newline+indent appends. All produce identical logical results across all 4 variable state combinations.

## Why method2 is Faster
Fewer string operations — ternary expansion avoids parameter table lookup when `_L_wide` is empty. Single condition evaluation vs compound boolean.
