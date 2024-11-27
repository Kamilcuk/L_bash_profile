import subprocess
import shlex
import tempfile


def run(what: str, *args):
    what = what % args
    cmd = shlex.split(what)
    print(f"+ {cmd}")
    subprocess.check_call(cmd)


def test_1():
    with tempfile.NamedTemporaryFile() as f:
        tmpf = f.name
        run("L_bash_profile profile %s 'f() { echo f; }; g() { f; echo g; }; g'", tmpf)
        run("cat %s", tmpf)
        run("L_bash_profile analyze %s", tmpf)
