# OpenCode Workflow for L_bash_profile

This directory contains profiling workflow configurations for OpenCode.

## Available Workflows

- **`profiling-workflow.yml`**: Configure OpenCode to use the L_bash_profile tool for profiling benchmarks
- **`quick-commands.md`**: Reference for common profiling commands

The workflows are designed to follow the methodology in `doc/PROFILING_WORKFLOW.md` and provide guided workflows for:
- Quick microbenchmarks (pure bash builtins)
- Shared-state benchmarks (regex, arrays, globals) 
- Pipeline/external command benchmarks
- Full system profiling
- Script profiling