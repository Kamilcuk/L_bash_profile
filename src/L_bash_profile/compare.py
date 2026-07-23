import contextlib
import os
import shlex
import statistics
import subprocess
import sys
import tempfile
import threading
import uuid
from enum import Enum
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple, Union
from concurrent.futures import ProcessPoolExecutor

import click
import clickdc
from tabulate import tabulate

from .common import bash_cmd, bash_cmd_env, qemu_output_drain_fifo


class Method(Enum):
    TIME = r"""
{before}
export TIMEFORMAT='{marker} %6R %6U %6S'
{repeat_start}
time {{
{script}
}}
{repeat_end}
{suffix}
"""
    QEMU = r"""
kill -0 $$
kill -0 $$; kill -0 $$
{before}
{repeat_start}
kill -0 $$
{script}
kill -0 $$
{repeat_end}
{suffix}
"""
    PERF = r"""
{before}
{repeat_start}
{script}
{repeat_end}
{suffix}
"""


@dataclass
class CompareArgs:
    prefix: str = clickdc.option(
        "-P",
        "--prefix",
        default="",
        show_default=True,
        help="Common prefix to run before each code snippet.",
    )
    suffix: str = clickdc.option(
        "-S",
        "--suffix",
        default="",
        show_default=True,
        help="Common suffix to run after each code snippet.",
    )
    method: Method = clickdc.option(
        "-m",
        "--method",
        default=Method.TIME,
        type=click.Choice(Method, case_sensitive=False),
        show_default=True,
        help="Comparison method: TIME (wall-clock), QEMU (instruction count), PERF (linux perf).",
    )
    repeat: int = clickdc.option(
        "-r",
        "--repeat",
        default=1,
        required=False,
        show_default=True,
        help="Repeat the script n times inside a loop. Do not use in QEMU mode (deterministic).",
    )
    qemu: bool = clickdc.option(
        "-q", "--qemu", is_flag=True, help="Shortcut for --method QEMU."
    )
    perf: bool = clickdc.option(
        "--perf", is_flag=True, help="Shortcut for --method PERF."
    )
    json: bool = clickdc.option(
        "-j", "--json", is_flag=True, help="Output comparison results as JSON."
    )
    show_output: bool = clickdc.option(
        "-o/-O",
        "--show-output/--no-show-output",
        default=True,
        help="Show stdout/stderr of the compared snippets (enabled by default).",
    )
    codes: Tuple[str, ...] = clickdc.argument(nargs=-1)


@dataclass
class QemuResult:
    samples: List[float]
    exit_code: int


@dataclass
class PerfResult:
    instructions: float
    exit_code: int


@dataclass
class TimeSample:
    real: float
    user: float
    sys: float


@dataclass
class TimeResult:
    samples: List[TimeSample]
    exit_code: int


@contextlib.contextmanager
def run_drain_thread(fifo: str, profile_out: str):
    drain_thread = threading.Thread(
        target=qemu_output_drain_fifo, args=(fifo, profile_out)
    )
    drain_thread.start()
    fifo_fd = os.open(fifo, os.O_WRONLY)
    try:
        yield fifo_fd
    finally:
        os.close(fifo_fd)
        drain_thread.join()


def _run_compare_snippet(
    i: int, args: CompareArgs, code: str
) -> Union[QemuResult, PerfResult, TimeResult]:
    print(
        f"Benchmarking {i + 1}/{len(args.codes)}: {shlex.quote(code)}",
        file=sys.stderr,
    )

    # Handle repeat logic
    if args.repeat <= 1:
        repeat_start = ""
        repeat_end = ""
    else:
        repeat_start = f"for ((_i=0; _i<{args.repeat}; _i++)); do"
        repeat_end = "done"

    before_cmd = args.prefix
    suffix_cmd = args.suffix
    script_template = args.method.value

    if args.method == Method.QEMU:
        return _run_qemu(
            script_template,
            before_cmd,
            suffix_cmd,
            code,
            repeat_start,
            repeat_end,
            args.show_output,
        )
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
        if args.method == Method.PERF:
            return _run_perf(script, args.show_output)
        else:  # TIME
            return _run_time(script, marker, args.show_output)


def _run_qemu(
    template: str,
    before: str,
    suffix: str,
    script_code: str,
    repeat_start: str,
    repeat_end: str,
    show_output: bool = False,
) -> QemuResult:
    with tempfile.TemporaryDirectory() as tmpdir:
        fifo = os.path.join(tmpdir, "fifo")
        os.mkfifo(fifo)
        profile_out = os.path.join(tmpdir, "out.txt")

        exit_code = 0
        with run_drain_thread(fifo, profile_out) as fifo_fd:
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
            proc = subprocess.run(
                cmd,
                pass_fds=[fifo_fd],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=bash_cmd_env(),
            )
            exit_code = proc.returncode
            if show_output:
                if proc.stdout:
                    sys.stdout.buffer.write(proc.stdout)
                    sys.stdout.flush()

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
        return QemuResult(samples=samples, exit_code=exit_code)


def _run_time(script: str, marker: str, show_output: bool = False) -> TimeResult:
    samples = []
    cmd = [*bash_cmd(), "-c", script, "bash"]
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=bash_cmd_env(),
    )
    if show_output:
        if proc.stdout:
            for line in proc.stdout.splitlines():
                if not line.startswith(marker + " "):
                    sys.stdout.write(line + "\n")
            sys.stdout.flush()

    # Bash 'time' output goes to stdout (since stderr redirected to stdout)
    if proc.stdout:
        for line in proc.stdout.splitlines():
            if line.startswith(marker + " "):
                parts = line.split()
                if len(parts) >= 4:
                    try:
                        # Capture real, user, system in seconds
                        samples.append(
                            TimeSample(
                                real=float(parts[1]),
                                user=float(parts[2]),
                                sys=float(parts[3]),
                            )
                        )
                    except ValueError:
                        continue
    return TimeResult(samples=samples, exit_code=proc.returncode)


def _run_perf(script: str, show_output: bool = False) -> PerfResult:
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
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=bash_cmd_env(),
    )
    if show_output:
        if proc.stdout:
            for line in proc.stdout.splitlines():
                if "instructions" not in line and "Performance counter stats" not in line and "seconds time elapsed" not in line and "seconds user" not in line and "seconds sys" not in line:
                    sys.stdout.write(line + "\n")
            sys.stdout.flush()

    # Parse perf output (now in stdout because stderr is redirected to stdout)
    if proc.stdout:
        for line in proc.stdout.splitlines():
            if "instructions" in line:
                # Example line: "         1,234,567      instructions              #    0.50  insn per cycle"
                parts = line.strip().split()
                if parts:
                    return PerfResult(
                        instructions=float(parts[0].replace(",", "").replace(".", "")),
                        exit_code=proc.returncode,
                    )
    return PerfResult(instructions=0.0, exit_code=proc.returncode)


class SequentialExecutor:
    def __enter__(self) -> "SequentialExecutor":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        pass

    def map(self, fn: Any, *iterables: Any) -> Any:
        return map(fn, *iterables)


def compare_cmd(args: CompareArgs) -> None:
    if not args.codes:
        print("Error: No code snippets provided.", file=sys.stderr)
        return

    if args.qemu:
        args.method = Method.QEMU
    if args.perf:
        args.method = Method.PERF

    if args.method == Method.QEMU and args.repeat > 1:
        print(
            "Warning: QEMU mode is deterministic. Using --repeat is highly discouraged as it adds redundant overhead.",
            file=sys.stderr,
        )

    executor = (
        ProcessPoolExecutor() if args.method == Method.QEMU else SequentialExecutor()
    )
    with executor:
        datas = list(
            executor.map(
                _run_compare_snippet,
                range(len(args.codes)),
                [args] * len(args.codes),
                args.codes,
            )
        )

    results: List[Dict[str, Union[float, str, int]]] = []
    previous_avg_real = None
    for i, (code, data) in enumerate(zip(args.codes, datas)):
        avg_real: float
        if isinstance(data, TimeResult):
            # TIME data
            reals = [s.real for s in data.samples]
            users = [s.user for s in data.samples]
            syss = [s.sys for s in data.samples]

            avg_real = statistics.mean(reals) if reals else 0
            avg_user = statistics.mean(users) if users else 0
            avg_sys = statistics.mean(syss) if syss else 0

            stddev_real = statistics.stdev(reals) if len(reals) > 1 else 0
            stddev_user = statistics.stdev(users) if len(users) > 1 else 0
            stddev_sys = statistics.stdev(syss) if len(syss) > 1 else 0
            total_real = sum(reals)
        elif isinstance(data, QemuResult):
            # QEMU data (list of floats)
            avg_real = statistics.mean(data.samples) if data.samples else 0
            avg_user = avg_sys = 0
            stddev_real = statistics.stdev(data.samples) if len(data.samples) > 1 else 0
            stddev_user = stddev_sys = 0
            total_real = sum(data.samples)
        elif isinstance(data, PerfResult):
            # Aggregate processing (PERF)
            avg_real = (
                data.instructions / args.repeat
                if args.repeat > 0
                else data.instructions
            )
            avg_user = avg_sys = stddev_real = stddev_user = stddev_sys = 0
            total_real = data.instructions
        else:
            avg_real = avg_user = avg_sys = stddev_real = stddev_user = stddev_sys = 0
            total_real = 0

        diff = 0 if previous_avg_real is None else avg_real - previous_avg_real
        previous_avg_real = avg_real

        exit_code = getattr(data, "exit_code", 0)
        res: Dict[str, Union[float, str, int]] = {
            "Code": code if code else "''",
            "ExitCode": exit_code,
        }
        if args.method == Method.QEMU:
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

    print(f"Comparison results (method: {args.method.name}, repeat: {args.repeat}):")
    print(tabulate(results, headers="keys", tablefmt="github", disable_numparse=True))
