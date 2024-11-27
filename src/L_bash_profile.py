#!/usr/bin/env python3

from __future__ import annotations

import marshal
import multiprocessing
import os
import pstats
import re
import shlex
import subprocess
import time
from collections import Counter
from dataclasses import astuple, dataclass, field
from datetime import timedelta
from functools import cached_property
from typing import Iterable, Optional, TypeVar, overload

import click
import clickdc
from graphviz import Digraph
from tabulate import tabulate

###############################################################################

T = TypeVar("T")
V1 = TypeVar("V1")
V2 = TypeVar("V2")
V3 = TypeVar("V3")


@overload
def zip_dicts(a: dict[T, V1], /) -> dict[T, tuple[V1]]: ...
@overload
def zip_dicts(a: dict[T, V1], b: dict[T, V2], /) -> dict[T, tuple[V1, V2]]: ...
@overload
def zip_dicts(
    a: dict[T, V1], b: dict[T, V2], c: dict[T, V3], /
) -> dict[T, tuple[V1, V2, V3]]: ...
def zip_dicts(*dicts):
    """Zip dictionaries to same keys and tuple values"""
    return dict((k, tuple(d[k] for d in dicts)) for k in dicts[0])


def dots_trim(v: str, width: int = 50) -> str:
    """if string is too long, trim it and add dots"""
    return v if len(v) <= width else (v[: width - 2] + "..")


def click_help():
    return click.help_option("-h", "--help")


def file_newer(a: str, b: str) -> bool:
    return (
        os.path.exists(a)
        and os.path.exists(b)
        and os.path.getctime(a) > os.path.getctime(b)
    )


def maybe_take_n(generator: Iterable[T], n: Optional[int]) -> Iterable[T]:
    """If n is ok, then take up to n elements"""
    if n and n > 0:
        return (a for _, a in zip(range(n), generator))
    else:
        return generator


def getdefault(e: list[T], idx: int, default: V1 = None) -> T | V1:
    try:
        return e[idx]
    except KeyError:
        return default


def us2s(us: int) -> float:
    return us / 1000000


###############################################################################


@dataclass(frozen=True, order=True)
class FunctionKey:
    """cProfile pstats file key"""

    filename: str
    lineno: int
    funcname: str


@dataclass
class Trace:
    level: int
    source: str
    lineno: int
    funcname: str


@dataclass
class Record:
    """Single line output from profiling information"""

    idx: int
    stamp_us: int
    cmd: str
    trace: list[Trace]
    spent_us: int = -1


class Records(list[Record]):
    """An array of records"""

    @property
    def sum_spent_us(self):
        return sum(x.spent_us for x in self)


@dataclass
class CallgraphNode:
    """Single node in the callgraph"""

    function: str
    spent_us: int = 0
    child_us: int = 0
    childs: dict[str, CallgraphNode] = field(default_factory=dict)


@dataclass
class AnalyzeArgs:
    linelimit: Optional[int] = clickdc.option(
        help="From the input file, parse only that many lines from the top. This is used to reduce the numebr of analyzed lines for testing"
    )
    dotcallgraph: Optional[str] = clickdc.option(
        "--dot", help="Output file for dot graph. Use xdot <file> to view."
    )
    dotcallgraph_limit: int = clickdc.option(
        "--dot-limit",
        default=3,
        show_default=True,
        help="When generating dot callgraph, limit the number of children of each point to max this number",
    )
    filterfunction: Optional[str] = clickdc.option(
        help="Only filter execution time of this particular function. Usefull for analysis of a single bash function execution"
    )
    pstatsfile: Optional[str] = clickdc.option(
        help="TODO: Generate python pstats file just like python cProfile file"
    )
    profilefile: str = clickdc.argument()


@dataclass
class RecordsSpentInterface:
    records: Records = field(default_factory=Records)
    spent: int = 0

    def add_record(self, rr: Record):
        self.records.append(rr)
        self.spent += rr.spent_us

    def get_example(self):
        t = next(
            (rr.trace[0] for rr in self.records if rr.trace),
            None,
        )
        return f"{t.source}:{t.lineno}" if t else ""


@dataclass
class FunctionData(RecordsSpentInterface):
    calls: int = 0

    def add(self, rr: Record, called: bool):
        self.add_record(rr)
        self.calls += called


@dataclass
class Timeit:
    """Measure time in section"""

    name: str = ""
    start: float = 0
    duration: float = 0

    def __enter__(self):
        self.start = time.time()

    def __exit__(self, *_):
        self.duration = time.time() - self.start
        if self.name:
            self.print()

    def print(self):
        print(f"{self.name} took {timedelta(seconds=self.duration)} seconds")


@dataclass
class CommandData(RecordsSpentInterface):
    callers: Counter[str] = field(default_factory=Counter)

    def add(self, rr: Record):
        self.add_record(rr)
        if rr.trace:
            self.callers.update([rr.trace[0].funcname])


@dataclass
class FunctionStats:
    called_count: int = 0
    recursive_call_count: int = 0
    tottime: float = 0
    cumtime: float = 0
    callers: dict[FunctionKey, FunctionStats] = field(default_factory=dict)


@dataclass
class PstatsStats:
    """cProfile pstats file statistics value"""

    nc: int = 0  # for the number of calls
    cc: int = 0  # how many times called recursively
    tt: int = 0  # for the total time spent in the given function (and excluding time made in calls to sub-functions)
    ct: int = 0  # is the cumulative time spent in this and all subfunctions (from invocation till exit
    callers: dict[FunctionKey, PstatsStats] = field(default_factory=dict)


@dataclass
class LineProcessor:
    """Processes lines from input file.
    Stores cached compile patterns.
    Exists to be multiprocessing-parallelized.
    """

    linergx: re.Pattern
    filterfunction_rgx: Optional[re.Pattern]

    def process_line(self, data: tuple[int, str]) -> Optional[Record]:
        lineno, line = data
        if self.linergx.match(line):
            # Fix shlex.split not able to parse $'\''
            line = line.replace(r"\'", "")
            try:
                arr = shlex.split(line)
            except Exception as e:
                print("ERROR: lineno:", lineno, " line:", repr(line), e)
                return
            assert (len(arr) - 3) % 4 == 0, f"{arr}"
            rr = Record(
                idx=lineno,
                stamp_us=int(arr[1]),
                cmd=arr[2],
                trace=[
                    Trace(
                        int(arr[i]),
                        arr[i + 1],
                        int(arr[i + 2]),
                        arr[i + 3],
                    )
                    for x in range((len(arr) - 3) // 4)
                    for i in [3 + 4 * x]
                ],
            )
            if self.filterfunction_rgx is not None:
                if not rr.trace or not self.filterfunction_rgx.match(
                    rr.trace[0].funcname
                ):
                    return
            return rr


@dataclass
class Analyzer:
    args: AnalyzeArgs
    records: list[Record] = field(default_factory=list)
    functions: dict[str, FunctionData] = field(default_factory=dict)
    commands: dict[str, CommandData] = field(default_factory=dict)

    def run(self):
        with Timeit(f"Reading {self.args.profilefile}"):
            self.read()
        with Timeit("Calculating time spent"):
            self.calculate_spent_time()
        with Timeit("Getting longest commands"):
            self.print_top_longest_commands()
        with Timeit("Getting longest functions"):
            self.print_top_longest_functions()
        if self.args.dotcallgraph:
            with Timeit("Generating dot callgraph"):
                self.extract_callgraph(self.args.dotcallgraph)
        if self.args.pstatsfile:
            with Timeit("Generting pstats file"):
                self.create_python_pstats_file(self.args.pstatsfile)
        self.print_stats()

    @cached_property
    def execution_time_us(self):
        return self.records[-1].stamp_us - self.records[0].stamp_us

    def print_stats(self):
        print()
        print(
            f"Command executed in {timedelta(microseconds=self.execution_time_us)}us, {len(self.records)} instructions, {len(self.functions)} functions."
        )

    def read(self):
        # read the data
        lp = LineProcessor(
            linergx=re.compile(r"^# [0-9]+ .+$"),
            filterfunction_rgx=(
                re.compile(self.args.filterfunction)
                if self.args.filterfunction
                else None
            ),
        )
        with open(self.args.profilefile, errors="replace") as f:
            with multiprocessing.Pool() as pool:
                generator = maybe_take_n(enumerate(f), self.args.linelimit)
                self.records = [x for x in pool.map(lp.process_line, generator) if x]

    def calculate_spent_time(self):
        # convert absolute timestamp to relative
        for i in range(len(self.records) - 1):
            self.records[i].spent_us = (
                self.records[i + 1].stamp_us - self.records[i].stamp_us
            )
        self.records.pop()

    def print_top_longest_commands(self):
        self.commands = {}
        for rr in self.records:
            self.commands.setdefault(rr.cmd, CommandData()).add(rr)

        def get_top_caller(v: CommandData, i: int):
            if len(v.callers) <= i:
                return ""
            x = v.callers.most_common()[i]
            return f"{x[0]} {x[1]}"

        longest_commands: list[dict] = [
            dict(
                percent=v.spent / self.execution_time_us * 100,
                spent_us=f"{v.spent:_}",
                cmd=dots_trim(cmd),
                calls=len(v.records),
                spentPerCall=f"{v.spent / len(v.records):_}",
                topCaller1=get_top_caller(v, 0),
                topCaller2=get_top_caller(v, 1),
                topCaller3=get_top_caller(v, 2),
                example=v.get_example(),
            )
            for cmd, v in sorted(
                self.commands.items(),
                key=lambda x: -x[1].spent,
            )[:20]
        ]
        print()
        print(f"Top {len(longest_commands)} cummulatively longest commands:")
        print(tabulate(longest_commands, headers="keys"))

    def extract_callgraph(self, outputfile: str):
        # Create callgraph
        callgraph = CallgraphNode("__entrypoint__")
        for record in self.records:
            call = callgraph
            for t in reversed(record.trace):
                call.child_us += record.spent_us
                call = call.childs.setdefault(t.funcname, CallgraphNode(t.funcname))
            call.spent_us += record.spent_us
        # print(callgraph)
        dot = Digraph()

        def callgraph_printer(parents: str, x: CallgraphNode, color: str = "#ffffff"):
            me = f"{parents}_{x.function}"
            dot.node(
                me,
                f"{x.function}\nspent={x.spent_us:_}us childs={x.child_us:_}us",
                color=color,
            )
            inc = 255 / len(x.childs) if x.childs else -1
            for idx, child in enumerate(
                maybe_take_n(
                    sorted(x.childs.values(), key=lambda x: -x.spent_us),
                    self.args.dotcallgraph_limit,
                )
            ):
                color = "#%2x%2x%2x" % (0xFF - int(inc * idx), 0x00, 0x00)
                dot.edge(
                    me,
                    f"{me}_{child.function}",
                    color=color,
                )
                callgraph_printer(me, child, color)

        callgraph_printer("", callgraph)
        with open(outputfile, "w") as f:
            print(dot.source, file=f)

    def print_top_longest_functions(self):
        self.functions = {}
        prevfunctions: set[str] = set()
        for r in self.records:
            currentfunctions = set(t.funcname for t in r.trace)
            if r.trace:
                t = r.trace[0]
                called = False
                for f in currentfunctions:
                    if f not in prevfunctions:
                        called = True
                self.functions.setdefault(t.funcname, FunctionData()).add(r, called)
            prevfunctions = currentfunctions

        longest_functions: list[dict] = [
            dict(
                percent=v.spent / self.execution_time_us * 100,
                spent_us=f"{v.spent:_}",
                funcname=func,
                calls=v.calls,
                spentPerCall=v.spent / v.calls,
                instructions=len(v.records),
                instructionsPerCall=len(v.records) / v.calls,
                example=v.get_example(),
            )
            for func, v in sorted(
                self.functions.items(),
                key=lambda x: -x[1].spent,
            )[:20]
        ]
        print()
        print(f"Top {len(longest_functions)} cummulatively longest functions:")
        print(tabulate(longest_functions, headers="keys"))


    def create_python_pstats_file(self, file: str):
        """
        https://github.com/python/cpython/blob/main/Lib/pstats.py#L160
        https://github.com/python/cpython/blob/main/Lib/cProfile.py#L63
        """
        # Extract function calls
        entrypoint = FunctionKey("~", 0, "<main>")
        stats: dict[FunctionKey, FunctionStats] = {}
        prevstack: list[FunctionKey] = [entrypoint]
        for rr in self.records:
            currentstack = [
                FunctionKey(x.source, x.lineno, x.funcname) for x in [entrypoint, *reversed(rr.trace)]
            ]
            for idx, key in enumerate(currentstack):
                elem = stats.setdefault(key, FunctionStats())
                elem.cumtime += us2s(rr.spent_us)
                if idx >= len(prevstack):
                    elem.called_count += 1
                    if elem.parent == key:
                        elem.recursive_call_count += 1
                elem.tottime += us2s(rr.spent_us)
            prevstack = currentstack

        def printer(prefix: str, key: FunctionKey, what: FunctionStats):
            print(
                f"{prefix}{key.filename}:{key.lineno}:{key.funcname} cc={what.called_count} rc={what.recursive_call_count} tt={what.tottime:f} ct={what.cumtime:f}"
            )
            for key2, val in what.callers.items():
                printer(prefix + "  ", key2, val)

        for key, val in root.callers.items():
            printer("", key, val)

        # Write pstats file

        def writer(what: FunctionStats):
            return (
                what.called_count,
                what.called_count - what.recursive_call_count,
                what.cumtime,
                what.tottime,
                {astuple(key): writer(val) for key, val in what.callers.items()},
            )

        stats = {astuple(key): writer(val) for key, val in root.callers.items()}
        with open(file, "wb") as f:
            marshal.dump(stats, f)
        print(f"pstats file written to {file}")


###############################################################################


@click.group(
    help="""
"""
)
@click_help()
def cli():
    pass


@cli.command(
    help="""
Generate profiling information of a given Bash script to PROFILEFILE.

Note: the script has to run in the current execution environment.
"""
)
@click.argument("profilefile")
@click.argument("script")
@click_help()
def profile(profilefile: str, script: str):
    cmd = """
LC_ALL=C
exec {FD}>"$1"
_trap_DEBUG() {
    local i txt=""
	for ((i = 1; i != ${#BASH_SOURCE[@]}; ++i)); do
		txt+=" $i ${BASH_SOURCE[i]@Q} ${BASH_LINENO[i]} ${FUNCNAME[i]@Q}"
    done
    echo "# ${EPOCHREALTIME//./} ${BASH_COMMAND@Q} $txt"
    # L_print_traceback
} >&$FD
# exec {BASH_XTRACEFD}> >(,ts --nano >&$FD)
trap '_trap_DEBUG' DEBUG
set -T
eval "$2"
: END
"""
    cmd = ["bash", "-c", cmd, "bash", profilefile, script]
    print(f"PROFILING: {cmd}")
    subprocess.run(cmd)
    print(f"PROFING ENDED, output in {profilefile}")
    # subprocess.run(["tail", "-n20", file])


@cli.command(
    help="""
Analyze profiling information.
    """
)
@click_help()
@clickdc.adddc("args", AnalyzeArgs)
def analyze(args: AnalyzeArgs):
    Analyzer(args).run()


@cli.command()
@click.argument("file")
def pstatsprint(file: str):
    ps = pstats.Stats(file)
    sortby = "cumulative"
    ps.strip_dirs().sort_stats(sortby).print_stats(
        0.3
    )  # plink around with this to get the results you need


###############################################################################

if __name__ == "__main__":
    cli.main()
