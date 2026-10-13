# Regex Capture Dispatch: if/elif vs case Benchmark

## Summary

For single-shot dispatch on BASH_REMATCH capture groups, performance depends on match position. if/elif short-circuits on early matches; case does constant work.

## Benchmark Results (QEMU instruction count)

| Match Position | if/elif | case | Winner |
|----------------|---------|------|--------|
| 1st (long)     | 61305   | 91137 | if/elif 49% faster |
| 2nd (regex)    | 72533   | 92496 | if/elif 28% faster |
| 3rd (here)     | 82493   | 93154 | if/elif 13% faster |
| 4th (with)     | 92852   | 94365 | if/elif 2% faster |
| 5th (cases)    | 103963  | 95680 | **case 8% faster** |
| None (nomatch) | 97698   | 86823 | **case 11% faster** |

## Complete Setup Script

Create and run:

```bash
mkdir -p ./temp
cat > ./temp/bench_regex.sh << 'EOF'
#!/usr/bin/env bash
setup_regex() {
    local a="$1"
    [[ $a =~ (long)|(regex)|(here)|(with)|(cases) ]]
}
case_if_elif() {
    if [[ -n ${BASH_REMATCH[1]} ]]; then :; 
    elif [[ -n ${BASH_REMATCH[2]} ]]; then :; 
    elif [[ -n ${BASH_REMATCH[3]} ]]; then :; 
    elif [[ -n ${BASH_REMATCH[4]} ]]; then :; 
    elif [[ -n ${BASH_REMATCH[5]} ]]; then :; fi
}
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

## Output for 1st Match (long)

```
L_bash_profile compare --qemu --prefix 'source ./temp/bench_regex.sh; setup_regex "long"' 'case_if_elif' 'case_case'
Comparison results (method: QEMU, repeat: 1):
| Code         | ExitCode   | Insn   | DeltaInsn   |
|--------------|------------|--------|-------------|
| case_if_elif | 0          | 61305  | -           |
| case_case    | 0          | 91137  | +29832      |
```

## Code Compared

```bash
# Setup (same for both)
a="long"
[[ $a =~ (long)|(regex)|(here)|(with)|(cases) ]]

# Method 1: if/elif chain
if [[ -n ${BASH_REMATCH[1]} ]]; then :; 
elif [[ -n ${BASH_REMATCH[2]} ]]; then :; 
elif [[ -n ${BASH_REMATCH[3]} ]]; then :; 
elif [[ -n ${BASH_REMATCH[4]} ]]; then :; 
elif [[ -n ${BASH_REMATCH[5]} ]]; then :; fi

# Method 2: case with parameter expansion dispatch
case "${BASH_REMATCH[1]:+1}${BASH_REMATCH[2]:+2}${BASH_REMATCH[3]:+3}${BASH_REMATCH[4]:+4}${BASH_REMATCH[5]:+5}" in
    1) :;;  2) :;;  3) :;;  4) :;;  5) :;; esac
```

## Why Results Vary by Position

- if/elif short-circuits: 1st match checks 1 condition, 5th match checks all 5
- case does constant work: one parameter expansion + one pattern match (~91-95K insn)
- Crossover at 5th match where if/elif cost exceeds case constant cost
- No match case: if/elif checks all 5, case does minimal work

## Methodology

L_bash_profile compare --qemu - deterministic instruction counting via QEMU user-mode emulation. Each snippet executed once (no loops). Setup file sourced in prefix to initialize BASH_REMATCH. State shared via sourced file, not inline prefix.