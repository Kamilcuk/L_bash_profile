#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import io
import marshal
import multiprocessing
import os
import pstats
import re
import shlex
import subprocess
import sys
import time
from collections import Counter
from dataclasses import astuple, dataclass, field
from datetime import timedelta
from functools import cached_property
from typing import Iterable, List, Optional, Tuple, TypeVar, Union, cast

import click
import clickdc
from graphviz import Digraph
from tabulate import tabulate

###############################################################################

T = TypeVar("T")
V = TypeVar("V")


def md5sum(data: str) -> str:
    return hashlib.md5(data.encode("utf-8")).hexdigest()


def clamp(n, minn, maxn):
    return max(min(maxn, n), minn)


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


def getdefault(e: list[T], idx: int, default: V = None) -> T | V:
    try:
        return e[idx]
    except (KeyError, IndexError):
        return default


def us2s(us: int) -> float:
    return us / 1000000


def fmtus(us: int) -> str:
    return f"{us:f}s"


def flatten(x: list[list[T]]) -> Iterable[T]:
    return (item for sublist in x for item in sublist)


def asgroups(x: Iterable[T], n: int) -> Iterable[list[T]]:
    i = 1
    group: list[T] = []
    for line in x:
        group.append(line)
        if i == n:
            yield group
            group = []
            i = 1
        else:
            i += 1
    if group:
        yield group


###############################################################################


@dataclass
class Integer:
    v: int = 0

    def inc(self):
        self.v += 1
        return self.v - 1


@dataclass
class RedGreenHue:
    elems: int

    def color(self, idx: int) -> Optional[str]:
        if self.elems == 0:
            return None
        val = int(0xFF * 2 / self.elems * idx)
        color = "#%02x%02x%02x" % (
            0xFF - val if 0 <= val < 0xFF else 0x00,
            val - 0xFF if 0xFF <= val else 0x00,
            0x00,
        )
        return color


@dataclass(frozen=True, order=True)
class FunctionKey:
    """To uniquely identify a function."""

    filename: str = ""
    lineno: int = -1
    funcname: str = ""

    def __str__(self):
        return f"{self.filename}:{self.lineno}({self.funcname})"


@dataclass
class Record:
    """Single line output from profiling information. Represents one instruction"""

    idx: int
    """Instruction number"""
    stamp_us: int
    """The timestamp as generated by EPOCHREALTIME"""
    pid: int
    """$BASPID"""
    cmd: str
    """$BASH_COMMAND"""
    level: int
    """${#BASH_SOURCE[@]}"""
    lineno: int
    """$LINENO"""
    source: str
    """$BASH_SOURCE, might be empty"""
    funcname: str
    """$BASH_FUNCNAME, might be empty"""
    spent_us: int = -1
    """How long did the instruction take? Substraction of EPOCHREALTIME from the next instruction"""

    def function(self):
        return FunctionKey(self.source, self.lineno, self.funcname)


class Records(List[Record]):
    """An array of records"""

    @property
    def sum_spent_us(self):
        return sum(x.spent_us for x in self)


@dataclass
class CmdStats:
    cmd: str
    callcount: int = 0
    totaltime: int = 0


@dataclass
class CallgraphNode:
    """Single node in the callgraph tree"""

    function: FunctionKey = field(default_factory=FunctionKey)
    records: list[Union[Record, CallgraphNode]] = field(default_factory=list)
    parent: Optional[CallgraphNode] = None

    @property
    def key(self):
        return self.function

    @cached_property
    def level(self) -> int:
        return 1 + (self.parent.level if self.parent else -1)

    @cached_property
    def inlinetime(self) -> int:
        return sum(rr.spent_us for rr in self.records if isinstance(rr, Record))

    @cached_property
    def childtime(self) -> int:
        return sum(rr.totaltime for rr in self.records if isinstance(rr, CallgraphNode))

    @cached_property
    def records_cnt(self) -> int:
        return sum(
            rr.records_cnt if isinstance(rr, CallgraphNode) else 1
            for rr in self.records
        )

    @cached_property
    def totaltime(self) -> int:
        return self.inlinetime + self.childtime


@dataclass
class CallstatsNode:
    """Single statistics node in the callgraph tree"""

    function: FunctionKey = field(default_factory=FunctionKey)
    """An index to the function to unique identify the node"""
    primitivecallcount: int = 0
    """How many times this function was called from the parent that is not recursive?"""
    recursivecallcount: int = 0
    """How many times this function was called where the parent is itself?"""
    children: dict[FunctionKey, CallstatsNode] = field(default_factory=dict)
    """functions called by this function"""
    cmdstats: dict[str, CmdStats] = field(default_factory=dict)
    """The commands executed by the function"""

    def add_record(self, r: Record):
        s = self.cmdstats.setdefault(r.cmd, CmdStats(r.cmd))
        s.callcount += 1
        s.totaltime += r.spent_us

    @cached_property
    def inlinetime(self) -> int:
        """How much time was spent in this node excluding subcalls"""
        return sum(s.totaltime for s in self.cmdstats.values())

    @cached_property
    def childtime(self) -> int:
        """How much time was spent in this node only in subcalls"""
        return sum(s.totaltime for s in self.children.values())

    @property
    def totaltime(self) -> int:
        return self.inlinetime + self.childtime

    @property
    def callcount(self) -> int:
        return self.primitivecallcount + self.recursivecallcount

    def merge(self, o: CallstatsNode):
        assert self.function == o.function, f"{self.function} {o.function}"
        self.primitivecallcount += o.primitivecallcount
        self.recursivecallcount += o.recursivecallcount
        for k, v in o.cmdstats.items():
            s = self.cmdstats.setdefault(k, CmdStats(k))
            s.callcount += v.callcount
            s.totaltime += v.totaltime
        for k, v in o.children.items():
            self.children.setdefault(k, CallstatsNode(k)).merge(v)


@dataclass
class Pstatsnocallers:
    """Statistics for pstats python module"""

    callcount: int = 0
    primitivecallcount: int = 0
    inlinetime: float = 0
    totaltime: float = 0


@dataclass
class Pstats(Pstatsnocallers):
    """Statistics for pstats python module"""

    callers: dict[FunctionKey, Pstatsnocallers] = field(default_factory=dict)


@dataclass
class AnalyzeArgs:
    """Command line arguments"""

    showtimes: Optional[bool] = clickdc.option(
        help="Show processing times in the output"
    )
    linelimit: Optional[int] = clickdc.option(
        help="From the input file, parse only that many lines from the top. This is used to reduce the numebr of analyzed lines for testing"
    )

    callgraph: Optional[str] = clickdc.option(
        help="Output file for dot callgraph file. Use for example `xdot <file>` to view.",
    )
    callstats: Optional[str] = clickdc.option(
        help="Output file for dot callstats file. Similar to full callgraph, but with statistics of function calls.",
    )
    callstatscmds: Optional[bool] = clickdc.option(
        help="Add commands to callstats graph"
    )
    pstats: Optional[str] = clickdc.option(
        help="Generate python pstats file just like python cProfile file"
    )
    dumprecords: Optional[str] = clickdc.option(
        help="Dump callgraph in text format to a file command by command, call by call.",
    )

    dotlimit: Optional[int] = clickdc.option(
        default=0,
        show_default=True,
        help="""
        When generating dot callgraph or callstats,
        limit the number of children of each point to max this number.
        Use to reduce big callgraphs where you do not see anything.
        """,
    )
    filterfunction: Optional[str] = clickdc.option(
        help="""
            Filter processing to callgraph roots from this function.
            Usefull for analysis of a single bash function execution
            """
    )

    profilefile: io.TextIOBase = clickdc.argument(
        type=click.File(errors="replace", lazy=True),
        required=False,
        default=io.TextIOWrapper(sys.stdin.buffer, errors="ignore"),
    )


@dataclass
class RecordsSpentInterface:
    records: Records = field(default_factory=Records)
    spent: int = 0

    def add_record(self, rr: Record):
        self.records.append(rr)
        self.spent += rr.spent_us

    def get_example(self):
        cmdcnt = Counter(r.cmd for r in self.records)
        most_common_cmd: str = cmdcnt.most_common(1)[0][0]
        r: Record = next(r for r in self.records if r.cmd == most_common_cmd)
        return f"{r.source or '~'}:{r.lineno}"


@dataclass
class FunctionStats(RecordsSpentInterface):
    """Accumulated data about a single function"""

    calls: int = 0


@dataclass
class Timeit:
    """Measure time of a section"""

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
class CommandStats(RecordsSpentInterface):
    """Accumulated data about a single command"""

    callers: Counter[str] = field(default_factory=Counter)

    def add(self, rr: Record):
        self.add_record(rr)
        self.callers.update([rr.funcname])


# List of bash scripts used for profiling.
PROFILEMETHODS: dict[str, str] = {
    "XTRACE": r"""
export BASH_XTRACEFD PS4='+ ${EPOCHREALTIME//[.,]} ${BASHPID:-${BASH_SUBSHELL:-$$}} ${#BASH_SOURCE[@]} ${LINENO:-0} ${BASH_SOURCE[0]:-<} ${FUNCNAME[0]:->} '
exec {BASH_XTRACEFD}>"$1"
shift
%BEFORE%
set -x
%SCRIPT%
: END
""",
    "DEBUG": r"""
set -T
exec {_L_bash_profile_fd}>"$1"
shift
%BEFORE%
trap 'printf "# %s %s %s %s %q %q %q\n" "${EPOCHREALTIME//[.,]}" "${BASHPID:-${BASH_SUBSHELL:-$$}}" "${#BASH_SOURCE[@]}" "${LINENO:-0}" "${BASH_SOURCE[0]:-<}" "${FUNCNAME[0]:->}" "$BASH_COMMAND" >&"$_L_bash_profile_fd"' DEBUG
%SCRIPT%
: END
""",
    "VAR": r"""
set -T
readonly _L_bash_profile_file=$1
shift
declare -a _L_bash_profile_var='()'
%BEFORE%
trap 'printf -v "_L_bash_profile_var[${#_L_bash_profile_var[@]}]" "# %s %s %s %s %q %q %q" "${EPOCHREALTIME//[.,]}" "${BASHPID:-${BASH_SUBSHELL:-$$}}" "${#BASH_SOURCE[@]}" "${LINENO:-0}" "${BASH_SOURCE[0]:-<}" "${FUNCNAME[0]:->}" "$BASH_COMMAND"' DEBUG
%SCRIPT%
printf "%s\n" "${_L_bash_profile_var[@]}" >"$_L_bash_profile_file"
""",
}
PROFILEMETHODS.update(
    {
        "1": PROFILEMETHODS["XTRACE"],
        "2": PROFILEMETHODS["DEBUG"],
        "3": PROFILEMETHODS["VAR"],
    }
)


@dataclass
class LineProcessor:
    """Processes lines from input file.
    Stores cached compile patterns.
    Exists to be multiprocessing-parallelized.
    Synchronize with profiling bash script.
    """

    def process_line(self, data: list[tuple[int, str]]) -> list[Record]:
        # data = data if isinstance(data, list) else [data]
        ret: list[Record] = []
        for lineno, line in data:
            try:
                if line.startswith("# "):
                    # Fix shlex.split not able to parse $'\''
                    line = line.replace(r"\'", "")
                    arr = shlex.split(line)
                    rr = Record(
                        idx=lineno,
                        stamp_us=int(arr[1]),
                        pid=int(arr[2]),
                        cmd=" ".join(arr[7:]),
                        level=int(arr[3]) + 1,
                        lineno=int(arr[4]),
                        source=arr[5],
                        funcname=arr[6],
                    )
                    ret.append(rr)
                elif line.startswith("+"):
                    # Fix shlex.split not able to parse $'\''
                    line = line.replace(r"\'", "")
                    arr = shlex.split(line)
                    rr = Record(
                        idx=lineno,
                        stamp_us=int(arr[1]),
                        pid=int(arr[2]),
                        cmd=repr(" ".join(arr[7:])),  # arr[6],
                        level=int(arr[3]) + 1,  # len(arr[0]),
                        lineno=int(arr[4]),
                        source=arr[5],
                        funcname=arr[6],
                    )
                    ret.append(rr)
            except Exception:
                # print("ERROR: lineno:", lineno, " line:", repr(line), e)
                # raise
                # break
                continue
        return ret


@dataclass
class Analyzer:
    args: AnalyzeArgs
    records: list[Record] = field(default_factory=list)

    def run(self):
        with self.timeit(f"Reading {self.args.profilefile}"):
            self.read()
        with self.timeit("Calculating traces and time spent"):
            self.calculate_records_spent_time()
        with self.timeit("Getting longest commands"):
            self.print_top_longest_commands()
        with self.timeit("Getting longest functions"):
            self.print_top_longest_functions()
        if self.args.dumprecords:
            self.dump_records(self.args.dumprecords)
        if self.args.callgraph:
            self.generate_dot_callgraph(self.args.callgraph)
        if self.args.callstats:
            self.generate_dot_callstats(self.args.callstats)
        if self.args.pstats:
            with self.timeit("Generting pstats file"):
                self.create_python_pstats_file(self.args.pstats)
        self.print_stats()

    def timeit(self, name: str):
        return Timeit(name if self.args.showtimes else "")

    def print_stats(self):
        print(
            f"Script executed in {timedelta(microseconds=self.get_callgraph.totaltime)}us, {len(self.records)} instructions, {len(self.functions)} functions."
        )

    def read(self):
        # read the data
        lp = LineProcessor()
        with self.args.profilefile as f:
            with multiprocessing.Pool() as pool:
                generator = asgroups(
                    maybe_take_n(enumerate(f), self.args.linelimit), 100
                )
                self.records = sorted(
                    flatten(pool.map(lp.process_line, generator)), key=lambda x: x.idx
                )

    def calculate_records_spent_time(self):
        # convert absolute timestamp to relative
        for i in range(len(self.records) - 1):
            self.records[i].spent_us = (
                self.records[i + 1].stamp_us - self.records[i].stamp_us
            )
        self.records.pop()

    @cached_property
    def get_callgraph(self):
        callgraph = CallgraphNode()
        curnode = callgraph
        curlevel = 1
        for rr in self.records:
            if rr.level > curlevel:
                newnode = CallgraphNode(rr.function(), parent=curnode)
                curnode.records.append(newnode)
                curnode = newnode
            elif rr.level < curlevel:
                for i in range(curlevel - rr.level):
                    assert curnode.parent
                    curnode = curnode.parent
            curlevel = rr.level
            curnode.records.append(rr)

        if self.args.filterfunction:
            funcnamergx = re.compile(self.args.filterfunction)
            callgraph2 = CallgraphNode()

            def traverse_to_filter(node: CallgraphNode):
                # print("MATCH", node.function.funcname, funcnamergx)
                if funcnamergx.match(node.function.funcname):
                    node.parent = callgraph2
                    callgraph2.records.append(node)
                else:
                    for rr in node.records:
                        if isinstance(rr, CallgraphNode):
                            # print(f"MATCH @ {rr.function}")
                            traverse_to_filter(rr)

            traverse_to_filter(callgraph)
            callgraph = callgraph2

        return callgraph

    def dump_records(self, file: str):
        callgraph = self.get_callgraph
        prefix = " >"

        def traverse_to_dump_records(f, node: CallgraphNode):
            for rr in node.records:
                if isinstance(rr, Record):
                    print(f"{prefix * node.level} {rr.spent_us:_}us {rr.cmd}", file=f)
                else:
                    print(f"{prefix * (node.level + 1)} call {rr.function}", file=f)
                    traverse_to_dump_records(f, rr)
                    print(
                        f"{prefix * (node.level + 1)} return {rr.function} total={rr.totaltime:_}us inline={rr.inlinetime:_}us child={rr.childtime:_}us",
                        file=f,
                    )

        with open(file, "w") as f:
            traverse_to_dump_records(f, callgraph)
        print("Records dumped to", file)

    def print_top_longest_commands(self):
        callgraph = self.get_callgraph
        self.commands: dict[str, CommandStats] = {}

        def traverse_for_top_longest_commands(node: CallgraphNode):
            for rr in node.records:
                if isinstance(rr, Record):
                    self.commands.setdefault(rr.cmd, CommandStats()).add(rr)
                else:
                    traverse_for_top_longest_commands(rr)

        traverse_for_top_longest_commands(callgraph)

        def get_top_caller(v: CommandStats, i: int):
            if len(v.callers) <= i:
                return ""
            x = v.callers.most_common()[i]
            return f"{x[0]} {x[1]}"

        def gen_text(cmd, v):
            return dict(
                percent=v.spent / callgraph.totaltime * 100,
                spent_us=f"{v.spent:_}",
                cmd=dots_trim(cmd),
                calls=len(v.records),
                spentPerCall=f"{v.spent / len(v.records):_}",
                topCaller1=get_top_caller(v, 0),
                topCaller2=get_top_caller(v, 1),
                topCaller3=get_top_caller(v, 2),
                example=v.get_example(),
            )

        longest_commands: list[dict] = [
            gen_text(cmd, v)
            for cmd, v in sorted(self.commands.items(), key=lambda x: -x[1].spent)[:20]
        ]
        print(f"Top {len(longest_commands)} cummulatively longest commands:")
        print(tabulate(longest_commands, headers="keys"))
        print()
        #
        longest_commands_per_call: list[dict] = [
            gen_text(cmd, v)
            for cmd, v in sorted(
                self.commands.items(), key=lambda x: -x[1].spent / len(x[1].records)
            )[:20]
        ]
        print(
            f"Top {len(longest_commands_per_call)} cummulatively longest commands per call:"
        )
        print(tabulate(longest_commands_per_call, headers="keys"))
        print()

    def print_top_longest_functions(self):
        callgraph = self.get_callgraph
        self.functions: dict[FunctionKey, FunctionStats] = {}

        def traverse_for_top_longest_functions(node: CallgraphNode):
            for rr in node.records:
                if isinstance(rr, Record):
                    self.functions.setdefault(
                        node.function, FunctionStats()
                    ).add_record(rr)
                else:
                    tmp = self.functions.setdefault(rr.function, FunctionStats())
                    tmp.calls += 1
                    traverse_for_top_longest_functions(rr)

        traverse_for_top_longest_functions(callgraph)
        if FunctionKey() in self.functions:
            del self.functions[FunctionKey()]

        if not self.functions:
            print("No functions found")
            return

        def gen_func_desc(func: FunctionKey, v: FunctionStats):
            return dict(
                percent=v.spent / callgraph.totaltime * 100,
                spent_us=f"{v.spent:_}",
                funcname=func.funcname,
                calls=v.calls,
                spentPerCall=v.spent / v.calls if v.calls else 0,
                instructions=len(v.records),
                instructionsPerCall=len(v.records) / v.calls if v.calls else 0,
                location=f"{func.filename}:{func.lineno}",
            )

        longest_functions: list[dict] = [
            gen_func_desc(func, v)
            for func, v in sorted(self.functions.items(), key=lambda x: -x[1].spent)[
                :20
            ]
        ]
        print(f"Top {len(longest_functions)} cummulatively longest functions:")
        print(tabulate(longest_functions, headers="keys"))
        print()
        #
        longest_functions_per_call: list[dict] = [
            gen_func_desc(func, v)
            for func, v in sorted(
                self.functions.items(),
                key=lambda x: -x[1].spent / x[1].calls if x[1].calls else 0,
            )[:20]
        ]
        print(
            f"Top {len(longest_functions_per_call)} cummulatively longest functions per call:"
        )
        print(tabulate(longest_functions_per_call, headers="keys"))
        print()

    @cached_property
    def get_callstats(self):
        callgraph = self.get_callgraph

        def traverse_for_callstats(node: CallgraphNode) -> CallstatsNode:
            ret = CallstatsNode(node.function)
            for rr in node.records:
                if isinstance(rr, Record):
                    ret.add_record(rr)
                elif rr.function == node.function:
                    ret.merge(traverse_for_callstats(rr))
                    ret.recursivecallcount += 1
                else:
                    x = ret.children.setdefault(rr.function, CallstatsNode(rr.function))
                    x.merge(traverse_for_callstats(rr))
                    x.primitivecallcount += 1
            return ret

        return traverse_for_callstats(callgraph)

    def generate_dot_callgraph(self, outputfile: str):
        callgraph = self.get_callgraph
        dot = Digraph()
        index = Integer()

        def nextname():
            return f"{index.inc()}"

        def traverse_to_gen_callgraph(
            parent: Digraph, nodename: str, node: CallgraphNode
        ):
            parent.node(nodename, f"{node.function}")
            graph = Digraph("graph_" + nodename, graph_attr=dict(rank="same"))
            prevname = nodename
            for rr in node.records:
                childname = nextname()
                dot.edge(prevname, childname)
                prevname = childname
                if isinstance(rr, Record):
                    graph.node(childname, rr.cmd, shape="box")
                else:
                    traverse_to_gen_callgraph(graph, childname, rr)
            dot.edge(prevname, nodename)
            dot.subgraph(graph)

        traverse_to_gen_callgraph(dot, nextname(), callgraph)

        with open(outputfile, "w") as f:
            print(dot.source, file=f)
        print("Callgraph written to", outputfile)

    def generate_dot_callstats(self, outputfile: str):
        callstats = self.get_callstats
        dot = Digraph()

        def callstats_printer(
            parents: str, x: CallstatsNode, color: Optional[str] = None
        ):
            me = f"{parents}_{x.function.funcname}"
            dot.node(
                me,
                "\n".join(
                    [
                        f"{x.function.funcname}",
                        (
                            f"calls={x.callcount} total={x.totaltime:_}us percall={int(x.totaltime / (x.callcount or 1)):_}us"
                            if x.callcount
                            else f"total={x.totaltime:_}us"
                        ),
                        " ".join(
                            ([f"inline={x.inlinetime:_}us"] if x.inlinetime else [])
                            + ([f"childs={x.childtime:_}us"] if x.childtime else [])
                        ),
                    ]
                ),
                color=color,
            )
            nodechildren = list(x.children.values())
            children: list[Union[CallstatsNode, CmdStats]] = cast(
                list[Union[CallstatsNode, CmdStats]], nodechildren
            )
            if self.args.callstatscmds:
                children.extend(list(x.cmdstats.values()))
            children = list(
                maybe_take_n(
                    sorted(children, key=lambda x: -x.totaltime),
                    self.args.dotlimit,
                )
            )
            redgreenhue = RedGreenHue(len(children))
            for idx, child in enumerate(children):
                # print(val, inc, idx, len(x.childs), color)
                color = redgreenhue.color(idx)
                if isinstance(child, CallstatsNode):
                    dot.edge(
                        me,
                        f"{me}_{child.function.funcname}",
                        color=color,
                    )
                    callstats_printer(me, child, color)
                else:
                    childname = f"{me}_{md5sum(child.cmd)}"
                    dot.edge(me, childname, color=color)
                    dot.node(
                        childname,
                        "\n".join(
                            [
                                repr(child.cmd),
                                f"calls={child.callcount} spent={child.totaltime:_}us",
                                f"percall={int(child.totaltime / child.callcount):_}us",
                            ]
                        ),
                        color=color,
                        shape="box",
                    )

        callstats_printer("", callstats)
        with open(outputfile, "w") as f:
            print(dot.source, file=f)
        print("Callstats written to", outputfile)

    def create_python_pstats_file(self, file: str):
        """
        https://github.com/python/cpython/blob/main/Lib/pstats.py#L160
        https://github.com/python/cpython/blob/main/Lib/cProfile.py#L63
        """
        # Extract function calls
        callstats = self.get_callstats
        statsroot: dict[FunctionKey, Pstats] = {}

        def fillstats(node: CallstatsNode):
            nodestats = statsroot.setdefault(node.function, Pstats())
            nodestats.callcount += node.callcount
            nodestats.primitivecallcount += node.primitivecallcount
            nodestats.totaltime += us2s(node.totaltime)
            nodestats.inlinetime += us2s(node.inlinetime)
            for child in node.children.values():
                fillstats(child)
                childstats = statsroot.setdefault(
                    child.function, Pstats()
                ).callers.setdefault(node.function, Pstatsnocallers())
                # These are meaningless from my understanding.
                childstats.callcount += 1
                childstats.primitivecallcount += 1
                childstats.inlinetime += us2s(child.inlinetime)
                childstats.totaltime += us2s(child.totaltime)
                if child.function == node.function:
                    nodestats.totaltime -= us2s(child.totaltime)

        fillstats(callstats)

        # Write pstats file
        def writer(what: Pstats):
            return (
                what.primitivecallcount,
                what.callcount,
                what.inlinetime,
                what.totaltime,
                {
                    astuple(key): (
                        val.primitivecallcount,
                        val.callcount,
                        val.inlinetime,
                        val.totaltime,
                    )
                    for key, val in what.callers.items()
                },
            )

        pstats = {astuple(key): writer(val) for key, val in statsroot.items()}
        with open(file, "wb") as f:
            marshal.dump(pstats, f)
        print(f"pstats file written to {file}")


###############################################################################


@click.group(
    help="""
Profile execution of bash scripts.
""",
    epilog="""
Written by Kamil Cukrowski 2024. Licensed under GPLv3.
    """,
)
@click_help()
def cli():
    pass


@dataclass
class ProfileArgs:
    """Command line arguments"""

    output: Optional[io.FileIO] = clickdc.option(
        "-o",
        type=click.File("w", lazy=True),
        help="Output file for profiling information.",
    )
    method: str = clickdc.option(
        "-m",
        default="XTRACE",
        type=click.Choice(list(PROFILEMETHODS.keys()), case_sensitive=False),
        help="""
        Chooses the method to profile the script.
        1 or XTRACE uses set -x with BASH_XTRACEFD and FD4 to output the commands.
        2 or DEBUG uses trap DEBUG to output executed commands to a file.
        3 or VAR uses trap DEBUG to append commands to an array and then write it to a file on the end of execution.
        XTRACE is the fastest.
        DEBUG is the most reliable.
        VAR does not handle subshells.
        """,
    )
    repeat: int = clickdc.option(
        "-n", default=1, help="Repeat the script n times joined with newlines."
    )
    before: str = clickdc.option(
        "-b",
        help="Commands to run before the script. Use to set up the environment.",
        default="",
        required=False,
    )
    dryrun: bool = clickdc.option(
        help="Do not run the script, just print the generated script."
    )
    script: str = clickdc.argument()
    args: tuple[str, ...] = clickdc.argument(nargs=-1)


@cli.command(
    help="""
Generate profiling information of a given Bash script to PROFILEFILE.

The script has to run commands in the current execution environment.
Use `source ./script.sh` to run a script.

Further arguments to the script are passed as ARGS.
""",
    epilog="""
\b
Example:
    L_bash_profile profile -n10 'echo hello world' | L_bash_profile analyze
    L_bash_profile profile -n200 -b i=0 '((i)); [[ $i ]]; [[ "$i" ]]; [ "$i" ]; [ $i ]' | L_bash_profile analyze
    L_bash_profile profile -n500 -b 'f() { "$@"; }; g() { "$@"; }; i=1' 'f eval "(($i))"; g test "$i" = 0;' | L_bash_profile analyze
""",
)
@click_help()
@clickdc.adddc("args", ProfileArgs)
def profile(args: ProfileArgs):
    profilefile = (
        "/dev/stdout"
        if not args.output or args.output == sys.stdout
        else args.output.name
    )
    script = "\n".join([args.script] * args.repeat)
    script = PROFILEMETHODS[args.method].replace("%BEFORE%", args.before).replace("%SCRIPT%", script)
    cmd = ["bash", "-c", script, "bash", profilefile, *args.args]
    if args.dryrun:
        print(" ".join(shlex.quote(x) for x in cmd))
        exit()
    print(f"PROFILING: {shlex.quote(args.script)} to {profilefile}", file=sys.stderr)
    subprocess.run(cmd)
    print(f"PROFING ENDED, output in {profilefile}", file=sys.stderr)


@cli.command(
    help="""
Analyze profiling information stored in PROFILEFILE.
    """,
    epilog="""
\b
Example:
	L_bash_profile analyze profile.txt \\
		--dumprecords profile.records.txt \\
		--callgraph profile.callgraph.dot \\
		--callstats profile.callstats.dot \\
		--pstats profile.pstats \\
		--callstatscmds \\
		--dotlimit 3
    """,
)
@click_help()
@clickdc.adddc("args", AnalyzeArgs)
def analyze(args: AnalyzeArgs):
    Analyzer(args).run()


@cli.command(help="print pstats data")
@click.option("-r", "--raw", is_flag=True, help="Just print marshal file content")
@click.argument("file", type=click.File("rb", lazy=True))
@click_help()
def showpstats(raw: bool, file: io.FileIO):
    if raw:

        def sortthem(x: dict):
            return sorted(x.items())

        def printit(prefix, key, val):
            print(
                f"{prefix}{key[0]}:{key[1]}({key[2]})  cc={val[0]} nc={val[1]} tt={val[2]:f} ct={val[3]:f}"
            )

        stats = marshal.load(file)
        for key, val in sortthem(stats):
            printit("", key, val)
            for key2, val2 in sortthem(val[4] or {}):
                printit(" ^ ", key2, val2)
    else:
        ps = pstats.Stats(file.name)
        sortby = "cumulative"
        ps.strip_dirs().sort_stats(sortby).print_stats()
        # plink around with this to get the results you need


###############################################################################

if __name__ == "__main__":
    cli.main()
