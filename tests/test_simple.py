import subprocess
import shlex
import tempfile


def run(what: str, *args):
    what = what % tuple([shlex.quote(x) if isinstance(x, str) else x for x in args])
    cmd = shlex.split(what)
    cmdstr = " ".join(shlex.quote(x) for x in cmd)
    print(f"+ {cmdstr}")
    subprocess.check_call(cmd)
    print()


def test_1():
    with tempfile.NamedTemporaryFile() as f:
        tmpf = f.name
        run(
            "L_bash_profile profile --output %s 'f() { echo f; }; g() { f; echo g; }; g'",
            tmpf,
        )
        run("cat %s", tmpf)
        with tempfile.NamedTemporaryFile() as f2:
            dotf = f2.name
            run("L_bash_profile analyze --pstats %s %s", dotf, tmpf)
            run("L_bash_profile showpstats %s", dotf)
            run("L_bash_profile showpstats --raw %s", dotf)
