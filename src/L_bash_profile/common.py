from typing import TypeVar

import click

T = TypeVar("T")
V = TypeVar("V")


def click_help():
    return click.help_option("-h", "--help")


def qemu_output_drain_fifo(fifo_path: str, out_path: str):
    insn_count = 0
    with open(fifo_path, "rt", errors="ignore") as fin:
        with open(out_path, "wt") as fout:
            for line in fin:
                if line.startswith("Trace "):
                    insn_count += 1
                elif line.startswith("# 0 "):
                    # Existing long marker support
                    parts = line.split(" ", 3)
                    if len(parts) >= 3:
                        parts[1] = str(insn_count)
                        fout.write(" ".join(parts))
                        fout.flush()
                elif line.strip() == "S":
                    # Simple Start marker
                    fout.write(f"START {insn_count}\n")
                    fout.flush()
                elif line.strip() == "E":
                    # Simple End marker
                    fout.write(f"STOP {insn_count}\n")
                    fout.flush()
                else:
                    fout.write(line)
                    fout.flush()
