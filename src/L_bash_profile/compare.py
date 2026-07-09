import os
import shlex
import statistics
import subprocess
import sys
import tempfile
import threading
import uuid
from dataclasses import dataclass
from typing import Dict, List, Tuple, Union

import click
import clickdc
from tabulate import tabulate

from .common import bash_cmd, bash_cmd_env, qemu_output_drain_fifo

COMPARE_METHODS = {
    "TIME": r"""
{before}
export TIMEFORMAT='{marker} %6R %6U %6S'
{repeat_start}
time {{
{script}
}}
{repeat_end}
{suffix}
""",
    "QEMU": r"""
kill -0 $$
kill -0 $$; kill -0 $$
{before}
{repeat_start}
kill -0 $$
{script}
kill -0 $$
{repeat_end}
{suffix}
""",
    "PERF": r"""
{before}
{repeat_start}
{script}
{repeat_end}
{suffix}
""",
}


@dataclass
class CompareArgs:
    prefix: str = clickdc.option(
        "-P",
        "--prefix",
        default="",
        help="Common prefix to run before each code snippet.",
    )
    suffix: str = clickdc.option(
        "-S",
        "--suffix",
        default="",
        help="Common suffix to run after each code snippet.",
    )
    method: str = clickdc.option(
        "-m",
        "--method",
        default="TIME",
        type=click.Choice(list(COMPARE_METHODS.keys()), case_sensitive=False),
        help="Comparison method: TIME (wall-clock), QEMU (instruction count), PERF (linux perf).",
    )
    repeat: int = clickdc.option(
        "-r",
        "--repeat",
        default=1,
        required=False,
        help="Repeat the script n times inside a loop. Do not use in QEMU mode (deterministic).",
    )
    qemu: bool = clickdc.option(
        "--qemu", is_flag=True, help="Shortcut for --method QEMU."
    )
    perf: bool = clickdc.option(
        "--perf", is_flag=True, help="Shortcut for --method PERF."
    )
    json: bool = clickdc.option(
        "-j", "--json", is_flag=True, help="Output comparison results as JSON."
    )
    codes: Tuple[str, ...] = clickdc.argument(nargs=-1)


def _run_compare_snippet(
    args: CompareArgs, code: str
) -> Union[float, List[float], List[Dict[str, float]]]:
    method = args.method.upper()
    if args.qemu:
        method = "QEMU"
    if args.perf:
        method = "PERF"

    # Handle repeat logic: Always use a loop for consistency (warm vs cold parsing)
    repeat_start = f"for ((_i=0; _i<{args.repeat}; _i++)); do"
    repeat_end = "done"

    before_cmd = args.prefix
    suffix_cmd = args.suffix
    script_template = COMPARE_METHODS[method]

    if method == "QEMU":
        return _run_qemu(script_template, before_cmd, suffix_cmd, code, repeat_start, repeat_end)
    else:
        marker = str(uuid.uuid4())
        script = script_template.format(
            before=before_cmd,
            script=code,
            repeat_start=repeat_start,
            repeat_end=repeat_end,
            marker=marker,
            suffix=suffix_cmd,
        )
        if method == "PERF":
            return _run_perf(script)
        else:  # TIME
            return _run_time(script, marker)


def _run_qemu(template, before, suffix, script_code, repeat_start, repeat_end) -> List[float]:
    with tempfile.TemporaryDirectory() as tmpdir:
        fifo = os.path.join(tmpdir, "fifo")
        os.mkfifo(fifo)
        profile_out = os.path.join(tmpdir, "out.txt")

        drain_thread = threading.Thread(
            target=qemu_output_drain_fifo, args=(fifo, profile_out)
        )
        drain_thread.start()

        fifo_fd = os.open(fifo, os.O_WRONLY)
        try:
            full_script = template.format(
                before=before,
                script=script_code,
                repeat_start=repeat_start,
                repeat_end=repeat_end,
                fd=fifo_fd,
                suffix=suffix,
            )
            cmd = [
                "qemu-x86_64",
                "-one-insn-per-tb",
                "-d",
                "exec,strace",
                "-D",
                fifo,
                *bash_cmd(),
                "-c",
                full_script,
                "bash",
                "/dev/null",
            ]
            subprocess.run(cmd, pass_fds=[fifo_fd], capture_output=True, env=bash_cmd_env())
        finally:
            os.close(fifo_fd)
            drain_thread.join()

        # Parse out.txt for START and STOP markers
        samples = []
        last_start = None
        with open(profile_out, "r") as f:
            for line in f:
                if line.startswith("START "):
                    last_start = int(line.split(" ")[1])
                elif line.startswith("STOP ") and last_start is not None:
                    samples.append(float(int(line.split(" ")[1]) - last_start))
                    last_start = None
        return samples


def _run_time(script: str, marker: str) -> List[Dict[str, float]]:
    samples = []
    cmd = [*bash_cmd(), "-c", script, "bash"]
    proc = subprocess.run(cmd, capture_output=True, text=True, env=bash_cmd_env())
    # Bash 'time' output goes to stderr
    for line in proc.stderr.splitlines():
        if line.startswith(marker + " "):
            parts = line.split()
            if len(parts) >= 4:
                try:
                    # Capture real, user, system in seconds
                    samples.append(
                        {
                            "real": float(parts[1]),
                            "user": float(parts[2]),
                            "sys": float(parts[3]),
                        }
                    )
                except ValueError:
                    continue
    return samples


def _run_perf(script: str) -> float:
    # perf stat -e instructions bash -c ...
    cmd = [
        "perf",
        "stat",
        "-e",
        "instructions",
        "--",
        *bash_cmd(),
        "-c",
        script,
        "bash",
        "/dev/null",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, env=bash_cmd_env())
    # Parse perf output (stderr)
    for line in proc.stderr.splitlines():
        if "instructions" in line:
            # Example line: "         1,234,567      instructions              #    0.50  insn per cycle"
            parts = line.strip().split()
            if parts:
                return float(parts[0].replace(",", "").replace(".", ""))
    return 0.0


def compare_cmd(args: CompareArgs):
    if not args.codes:
        print("Error: No code snippets provided.", file=sys.stderr)
        return

    method = args.method.upper()
    if args.qemu:
        method = "QEMU"
    if args.perf:
        method = "PERF"

    if method == "QEMU" and args.repeat > 1:
        print(
            "Warning: QEMU mode is deterministic. Using --repeat is highly discouraged as it adds redundant overhead.",
            file=sys.stderr,
        )

    results = []
    previous_avg_real = None

    for i, code in enumerate(args.codes):
        print(
            f"Benchmarking {i + 1}/{len(args.codes)}: {shlex.quote(code)}",
            file=sys.stderr,
        )
        data = _run_compare_snippet(args, code)

        if isinstance(data, list):
            # Statistical processing for multiple samples (TIME, QEMU)
            if data and isinstance(data[0], dict):
                # TIME data
                reals = [s["real"] for s in data]
                users = [s["user"] for s in data]
                syss = [s["sys"] for s in data]

                avg_real = statistics.mean(reals) if reals else 0
                avg_user = statistics.mean(users) if users else 0
                avg_sys = statistics.mean(syss) if syss else 0

                stddev_real = statistics.stdev(reals) if len(reals) > 1 else 0
                stddev_user = statistics.stdev(users) if len(users) > 1 else 0
                stddev_sys = statistics.stdev(syss) if len(syss) > 1 else 0
                total_real = sum(reals)
            else:
                # QEMU data (list of floats)
                avg_real = statistics.mean(data) if data else 0
                avg_user = avg_sys = 0
                stddev_real = statistics.stdev(data) if len(data) > 1 else 0
                stddev_user = stddev_sys = 0
                total_real = sum(data)
        else:
            # Aggregate processing (PERF)
            avg_real = data / args.repeat if args.repeat > 0 else data
            avg_user = avg_sys = stddev_real = stddev_user = stddev_sys = 0
            total_real = data

        diff = 0 if i == 0 else avg_real - previous_avg_real
        previous_avg_real = avg_real

        res = {"Code": code if code else "''"}
        if method == "QEMU":
            res["Insn"] = f"{avg_real:.0f}"
            res["ΔInsn"] = f"{diff:+.0f}" if i > 0 else "-"
            if args.repeat > 1:
                res["±Insn"] = f"{stddev_real:.0f}"
                res["Total"] = int(total_real)
        else:
            res["Real(s)"] = f"{avg_real:.6f}"
            res["Δ(s)"] = f"{diff:+.6f}" if i > 0 else "-"
            res["±Real"] = f"{stddev_real:.6f}"
            res["User"] = f"{avg_user:.6f}"
            res["±User"] = f"{stddev_user:.6f}"
            res["Sys"] = f"{avg_sys:.6f}"
            res["±Sys"] = f"{stddev_sys:.6f}"

        results.append(res)

    if args.json:
        import json
        print(json.dumps(results, indent=2))
        return

    print(f"Comparison results (method: {method}, repeat: {args.repeat}):")
    print(tabulate(results, headers="keys", tablefmt="github", disable_numparse=True))
