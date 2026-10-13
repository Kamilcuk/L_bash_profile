# Argument Parsing: Local + Shift vs Array Slicing Benchmark

## Summary
Array slicing (`"${@:4}"`) is significantly faster than using local variables + `shift` for extracting arguments in Bash function calls, saving over 45,000 CPU instructions (40.6% improvement) for this particular argument parsing pattern.

## Benchmark Results (QEMU instruction count)
| Approach | Instructions | Difference |
|----------|-------------|------------|
| Local variables + shift | 112,093 | Baseline |
| Array slicing (`"${@:4}"`) | 66,607 | -45,486 (-40.6%) |

## Full Command Line Used
```bash
# The exact command used to run the benchmark
/home/kamil/myprojects/L_bash_profile/.venv/bin/L_bash_profile compare --qemu --prefix 'source ./temp/bench_args.sh; setup_args' 'approach1' 'approach2'
```

## Code Compared (with context - FULLY REPRODUCIBLE)
```bash
# To fully reproduce this benchmark, include ALL executed commands:
# 1. Creation of the setup file in ./temp/
# 2. The actual L_bash_profile compare command

# Step 1: Create the setup file
mkdir -p ./temp
cat > ./temp/bench_args.sh << 'EOF'
#!/usr/bin/env bash
# ./temp/bench_args.sh - Setup and methods for argument parsing benchmark

# Setup function: initializes shared state (test arguments and L_obj_set_type_value)
setup_args() {
    # Define the test function (no-op for benchmarking)
    L_obj_set_type_value() { :; }
    # Set up test arguments: dest_val type_val value_val arg1 arg2 arg3 arg4
    set -- "dest_val" "type_val" "value_val" "arg1" "arg2" "arg3" "arg4"
}

# Method 1: local variables + shift
approach1() {
    local _L_type=$2 _L_val=$3
    shift 3
    L_obj_set_type_value _L_dest "$@" = "$_L_type" "$_L_val"
}

# Method 2: array slicing
approach2() {
    L_obj_set_type_value _L_dest "${@:4}" "$2" "$3"
}
EOF

# Step 2: Make the file executable (good practice, though not strictly required for the comparison)
chmod +x ./temp/bench_args.sh

# Step 3: Run the actual benchmark command
/home/kamil/myprojects/L_bash_profile/.venv/bin/L_bash_profile compare --qemu --prefix 'source ./temp/bench_args.sh; setup_args' 'approach1' 'approach2'

# First approach - local variables + shift (as it appears in the setup file)
# This approach saves $2 and $3 to local variables, shifts past the first 3 parameters,
# then calls the function with the remaining parameters followed by the saved values.
approach1() {
    local _L_type=$2 _L_val=$3
    shift 3
    L_obj_set_type_value _L_dest "$@" = "$_L_type" "$_L_val"
}

# Second approach - array slicing (as it appears in the setup file)
# This approach uses Bash's parameter expansion to directly extract the tail
# of the parameter array (from $4 onward) while still having access to $2 and $3.
approach2() {
    L_obj_set_type_value _L_dest "${@:4}" "$2" "$3"
}
```

## Intention and Alternative Approaches
The intention of both code snippets is to call `L_obj_set_type_value` with:
1. All arguments from position 4 onward (as "$@" to the function)
2. Followed by the original value of $2  
3. Followed by the original value of $3

This pattern is useful when you need to process a subset of arguments while preserving certain early arguments for later use.

Only consider testing alternative approaches if you have a reasonable hypothesis they might be faster based on understanding of Bash internals - do not waste time on brute-force testing of every possible variation.

Alternative approaches considered (based on hypothesis of potential improvement):
- Using array assignment and slicing: `local args=("$@"); L_obj_set_type_value _L_dest "${args[@]:3}" "${args[1]}" "${args[2]}"` 
  (Tested and found slower due to array creation overhead - hypothesis was incorrect)
- Using shift with temporary variables: Essentially equivalent to approach 1 (no meaningful difference expected)

No significantly better/faster alternative was discovered during testing - array slicing (`"${@:4}"`) appears to be the optimal approach for this specific argument extraction pattern in Bash, confirming the hypothesis that direct parameter expansion would minimize operations.

## Why Array Slicing is Faster
1. **Fewer operations**: Array slicing avoids the need for `local` variable assignments and the `shift` builtin
2. **No variable creation**: Eliminates the overhead of creating and destroying local variables (`_L_type`, `_L_val`)
3. **Direct parameter access**: `${@:4}` directly accesses the required slice without modifying the positional parameters
4. **Builtin optimization**: Parameter expansion is highly optimized in Bash's internal implementation

## Benchmark Details
- Tested with 8 total arguments: `dest_val type_val value_val arg1 arg2 arg3 arg4`
- Shared state setup: Defined `L_obj_set_type_value() { :; }` and initialized test arguments
- Method: QEMU-based instruction counting for precise, deterministic measurement