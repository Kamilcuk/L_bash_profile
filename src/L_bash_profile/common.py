import os
import shutil
from typing import TypeVar

import click

T = TypeVar("T")
V = TypeVar("V")


def is_qemu_available() -> bool:
    """Check if qemu-x86_64 is available in PATH."""
    return shutil.which("qemu-x86_64") is not None


def bash_cmd():
    exe = shutil.which("bash") or "bash"
    return [exe, "--norc", "--noprofile"]


def bash_cmd_env():
    env = os.environ.copy()
    env.pop("BASH_ENV", None)
    env.pop("ENV", None)
    return env


def click_help():
    return click.help_option("-h", "--help")


def qemu_output_drain_fifo(fifo_path: str, out_path: str):
    insn_count = 0
    cumulative_overhead = 0
    last_kill_start = None
    buffered_marker_line = None
    guest_pid = None
    kill_insns = []
    kill_overhead = 0

    with open(fifo_path, "rt", errors="ignore") as fin:
        with open(out_path, "wt") as fout:
            for line in fin:
                if line.startswith("Trace "):
                    insn_count += 1
                elif " kill(" in line:
                    line_stripped = line.strip()
                    parts = line_stripped.split()
                    if len(parts) >= 2 and parts[1].startswith("kill("):
                        try:
                            pid_str = parts[0]
                            target_pid_str = parts[1][5:].split(",")[0]
                            if pid_str == target_pid_str:
                                pid = int(pid_str)
                                if guest_pid is None:
                                    guest_pid = pid
                                if pid == guest_pid:
                                    kill_insns.append(insn_count)
                                    n_kills = len(kill_insns)
                                    if n_kills == 3:
                                        kill_overhead = kill_insns[2] - kill_insns[1]

                                    if buffered_marker_line is not None:
                                        # Profile mode: this is kill_end of a trap
                                        last_kill_end = insn_count
                                        if last_kill_start is not None:
                                            overhead = last_kill_end - last_kill_start
                                            cumulative_overhead += overhead
                                        adjusted_stamp = last_kill_end - cumulative_overhead
                                        m_parts = buffered_marker_line.split(" ", 3)
                                        if len(m_parts) >= 3:
                                            m_parts[1] = str(adjusted_stamp)
                                            fout.write(" ".join(m_parts))
                                            fout.flush()
                                        buffered_marker_line = None
                                        last_kill_start = None
                                    else:
                                        # No buffered marker line
                                        # In profile mode, this is candidate for kill_start
                                        last_kill_start = insn_count

                                        # In compare mode, if we have subsequent pairs of kills (after calibration kills)
                                        if n_kills >= 5 and n_kills % 2 != 0:
                                            # This is an odd number of kills (starting from 5), meaning we just got E_i (the end of sample i)
                                            start_idx = n_kills - 2
                                            end_idx = n_kills - 1
                                            s_val = kill_insns[start_idx]
                                            e_val = kill_insns[end_idx]
                                            # Write START/STOP with overhead subtracted
                                            fout.write(f"START {s_val}\n")
                                            fout.write(f"STOP {e_val - kill_overhead}\n")
                                            fout.flush()
                        except Exception:
                            pass
                elif line.startswith("# 0 "):
                    buffered_marker_line = line
                elif " write(" in line and "# 0 " in line:
                    # Parse DEBUG trap output from write syscall trace
                    # Format: PID write(FD, BUF, LEN)# 0 PID LEVEL SOURCE FUNCNAME CMD
                    # The DEBUG trap output is appended after the write syscall trace
                    try:
                        # Extract the DEBUG trap output after the write syscall trace
                        # Line format: "PID write(FD, BUF, LEN)# 0 PID LEVEL SOURCE FUNCNAME CMD"
                        # The DEBUG trap output starts at "# 0 "
                        idx = line.index("# 0 ")
                        marker_line = line[idx:].rstrip("\n")
                        buffered_marker_line = marker_line + "\n"
                    except Exception:
                        pass
                elif line.strip() == "S" or ("write(" in line and line.strip().endswith(")S")):
                    # Simple Start marker fallback
                    fout.write(f"START {insn_count - cumulative_overhead}\n")
                    fout.flush()
                elif line.strip() == "E" or ("write(" in line and line.strip().endswith(")E")):
                    # Simple End marker fallback
                    fout.write(f"STOP {insn_count - cumulative_overhead}\n")
                    fout.flush()
                else:
                    if "write(" in line and (line.strip().endswith(")S") or line.strip().endswith(")E")):
                        pass
                    else:
                        fout.write(line)
                        fout.flush()
