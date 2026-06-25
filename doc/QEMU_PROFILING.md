# QEMU-Based High-Precision Bash Profiler

## Overview
This document describes a novel architecture for profiling Bash scripts at the instruction level with 100% determinism. It correlates high-level Bash commands with low-level CPU instructions using QEMU User-Mode Emulation and the Bash `DEBUG` trap.

## The Architecture

### 1. Shared Sink (The FIFO)
The core of the profiler is a **Named Pipe (FIFO)**. Both the QEMU host (logging CPU traces) and the Bash guest (logging command markers) write to this same pipe.

### 2. Causal Interleaving
Because QEMU executes the guest's `write()` system calls, it is able to interleave its own internal instruction logs (`Trace` lines) with the guest's output in perfect sequential order.
- **Log Format:**
  ```text
  Trace 0: 0x...
  Trace 0: 0x...
  MARKER: a=1
  Trace 0: 0x...
  Trace 0: 0x...
  MARKER: b=2
  ```

### 3. Precision and Determinism
- **Instruction Count:** By counting `Trace` lines between markers, we get the exact number of CPU instructions executed for a specific Bash command.
- **Determinism:** Unlike time-based profilers, instruction counting is not affected by CPU frequency scaling, background system load, or thermal throttling.

## Implementation Details

### Warm Calibration and Dual-Kill Boundary Subtraction
To achieve instruction-level precision down to a single instruction, `L_bash_profile` uses a dual-kill boundary technique:
1. **Calibration:** On startup, the profiler triggers three sequential `kill -0 $$` system calls. The first call warms up the builtin and resolves any lazy symbol bindings. The difference in CPU instructions between the second and third calls establishes `kill_overhead`, representing the baseline cost of executing a single `kill -0 $$` builtin command.
2. **Measurement:** For each code snippet (or command in `profile` mode), boundary markers are established using `kill -0 $$`.
3. **Overhead Subtraction:** The instruction counts of the boundary `kill` system calls are matched sequentially. The dynamic `kill_overhead` is subtracted from the delta to yield the pure, isolated execution cost of the target script snippet.

### The QEMU Command
```bash
qemu-x86_64 -one-insn-per-tb -d exec,strace -D /tmp/profile_fifo \
  bash --norc --noprofile -c 'kill -0 $$; kill -0 $$; ...'
```

### Baseline Costs (Approximate)
| Bash Operation | Net CPU Instructions |
| :--- | :--- |
| `trap` + `echo` | ~40,000 |
| `a=1` (Assignment) | ~300 - 500 |
| `$((1+1))` (Arithmetic) | ~6,000 |
| `$(echo 1)` (Subshell) | ~60,000+ |

## Key Findings
1. **Subshell Penalty:** Spawning a subshell is nearly 200x more expensive than a simple assignment.
2. **Interpreter Overhead:** Most of the cost in a simple command is the interpreter parsing the line, not the operation itself.
3. **Accuracy:** This method can detect the instruction cost of a single semicolon.

## Potential for `L_lib.sh`
This architecture can be integrated into a new tool, `L_profile`, which automatically calculates the instruction delta for every line of code, allowing developers to identify high-cost Bash idioms with surgical precision.
