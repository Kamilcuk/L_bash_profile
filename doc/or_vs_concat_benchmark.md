# String Empty Check: Concatenation vs OR Benchmark

## Summary

`[[ -n $a$b ]]` vs `[[ -n $a || -n $b ]]` are essentially tied (~1-2% difference, within noise).

## Benchmark Results (QEMU instruction count)

| Case | Concat `[[ -n $a$b ]]` | OR `[[ -n $a || -n $b ]]` | Winner |
|------|------------------------|---------------------------|--------|
| both empty | 33,733 | 34,351 | concat +1.8% |
| `a` set | 32,730 | 32,295 | OR +1.3% |
| `b` set | 32,728 | 33,340 | concat +1.9% |
| both set | 34,187 | 33,603 | OR +1.7% |

## Complete Setup Script

Create `./temp/bench_or.sh`:

```bash
mkdir -p ./temp
cat > ./temp/bench_or.sh << 'EOF'
#!/usr/bin/env bash
# ./temp/bench_or.sh - Benchmark string empty check methods

# Test both empty
test_concat_empty() { [[ -n $a$b ]]; }
test_or_empty() { [[ -n $a || -n $b ]]; }

# Test a set
test_concat_a() { [[ -n $a$b ]]; }
test_or_a() { [[ -n $a || -n $b ]]; }

# Test b set
test_concat_b() { [[ -n $a$b ]]; }
test_or_b() { [[ -n $a || -n $b ]]; }

# Test both set
test_concat_both() { [[ -n $a$b ]]; }
test_or_both() { [[ -n $a || -n $b ]]; }
EOF
```

## Run the Benchmark

```bash
# Test each case
L_bash_profile compare --qemu --prefix 'source ./temp/bench_or.sh; a=; b=' 'test_concat_empty' 'test_or_empty'
L_bash_profile compare --qemu --prefix 'source ./temp/bench_or.sh; a=x; b=' 'test_concat_a' 'test_or_a'
L_bash_profile compare --qemu --prefix 'source ./temp/bench_or.sh; a=; b=x' 'test_concat_b' 'test_or_b'
L_bash_profile compare --qemu --prefix 'source ./temp/bench_or.sh; a=x; b=y' 'test_concat_both' 'test_or_both'
```

## Output Example (both empty)

```
Comparison results (method: QEMU, repeat: 1):
| Code         | ExitCode   | Insn   | DeltaInsn   |
|--------------|------------|--------|-------------|
| test_concat_empty | 0       | 33733  | -           |
| test_or_empty     | 0       | 34351  | +618        |
```

## Why Results Are Tied

Both short-circuit differently:
- **Concat** (`$a$b`): Evaluates left-to-right, stops at first non-empty character
- **OR** (`||`): Evaluates left operand, stops if true

The bytecode paths are nearly identical in cost. Use whichever reads clearer for your code.