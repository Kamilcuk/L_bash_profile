import subprocess
import shlex
import tempfile

import pytest

from L_bash_profile.common import is_qemu_available


def run(what: str, *args):
    what = what % tuple([shlex.quote(x) if isinstance(x, str) else x for x in args])
    cmd = shlex.split(what)
    cmdstr = " ".join(shlex.quote(x) for x in cmd)
    print(f"+ {cmdstr}")
    subprocess.check_call(cmd)
    print()


def test_1():
    with tempfile.NamedTemporaryFile(prefix="L_bash_profile_test_", suffix=".txt") as f:
        tmpf = f.name
        run(
            "L_bash_profile profile --output %s 'f() { echo f; }; g() { f; echo g; }; g'",
            tmpf,
        )
        run("cat %s", tmpf)
        with tempfile.NamedTemporaryFile(prefix="L_bash_profile_test_", suffix=".pstats") as f2:
            dotf = f2.name
            run("L_bash_profile analyze --pstats %s %s", dotf, tmpf)
            run("L_bash_profile showpstats %s", dotf)
            run("L_bash_profile showpstats --raw %s", dotf)


def test_qemu():
    if not is_qemu_available():
        pytest.skip("QEMU not available")
    with tempfile.NamedTemporaryFile(prefix="L_bash_profile_test_", suffix=".txt") as f:
        tmpf = f.name
        run("L_bash_profile profile --qemu -o %s 'a=1; b=2; c=$((a+b))'", tmpf)
        run("L_bash_profile analyze --qemu %s", tmpf)


def test_run():
    if not is_qemu_available():
        pytest.skip("QEMU not available")
    run("L_bash_profile run --qemu --callstatscmds 'f() { :; }; f'")


def test_compare():
    run("L_bash_profile compare --prefix 'a=1' --suffix 'echo $a' 'a=2'")
    if not is_qemu_available():
        pytest.skip("QEMU not available")
    run("L_bash_profile compare --qemu --prefix 'a=1' --suffix 'echo $a' 'a=2'")


def test_compare_sanity():
    if not is_qemu_available():
        pytest.skip("QEMU not available")
    # Run compare and capture output
    cmd = shlex.split("L_bash_profile compare -m qemu '' 'a=1'")
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    stdout = proc.stdout
    print(stdout)

    # Parse the Insn values
    lines = [line.strip() for line in stdout.splitlines() if "|" in line]
    data_lines = [ln for ln in lines if "Code" not in ln and "---" not in ln]

    assert len(data_lines) == 2

    parts_empty = [p.strip() for p in data_lines[0].split("|") if p.strip()]
    parts_a1 = [p.strip() for p in data_lines[1].split("|") if p.strip()]

    assert parts_empty[1] == "0"
    assert parts_a1[1] == "0"

    empty_insn = int(parts_empty[2])
    a1_insn = int(parts_a1[2])

    print(f"Parsed empty_insn: {empty_insn}, a1_insn: {a1_insn}")

    assert empty_insn >= 0
    assert a1_insn > empty_insn
    assert a1_insn > 1000


def test_json_output():
    import json
    # Test L_bash_profile run --json
    cmd = shlex.split("L_bash_profile run --json 'f() { :; }; f'")
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(proc.stdout)
    assert "total_time" in data
    assert "commands" in data
    assert "functions" in data
    assert any(f["funcname"] == "f" for f in data["functions"])

    if not is_qemu_available():
        pytest.skip("QEMU not available")

    # Test L_bash_profile compare --json
    cmd_compare = shlex.split("L_bash_profile compare --qemu --json '' 'a=1'")
    proc_compare = subprocess.run(cmd_compare, capture_output=True, text=True, check=True)
    data_compare = json.loads(proc_compare.stdout)
    assert len(data_compare) == 2
    assert data_compare[0]["Code"] == "''"
    assert "ExitCode" in data_compare[0]
    assert data_compare[0]["ExitCode"] == 0
    assert "Insn" in data_compare[0]


def test_compare_exit_codes():
    import json
    cmd = shlex.split("L_bash_profile compare --json 'exit 0' 'exit 42'")
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(proc.stdout)
    assert len(data) == 2
    assert data[0]["Code"] == "exit 0"
    assert data[0]["ExitCode"] == 0
    assert data[1]["Code"] == "exit 42"
    assert data[1]["ExitCode"] == 42


def test_compare_show_output():
    cmd = shlex.split("L_bash_profile compare -o 'echo MY_STDOUT_TEST_VAL' 'echo MY_STDERR_TEST_VAL >&2'")
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    assert "MY_STDOUT_TEST_VAL" in proc.stdout
    assert "MY_STDERR_TEST_VAL" in proc.stdout


def test_compare_qemu_show_output():
    if not is_qemu_available():
        pytest.skip("QEMU not available")
    cmd = shlex.split("L_bash_profile compare -q -o 'echo MY_QEMU_STDOUT_TEST' 'echo MY_QEMU_STDERR_TEST >&2'")
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    assert "MY_QEMU_STDOUT_TEST" in proc.stdout
    assert "MY_QEMU_STDERR_TEST" in proc.stdout


def test_subprocess_kill():
    if not is_qemu_available():
        pytest.skip("QEMU not available")
    # Spawns a background sleep, checks if alive with kill -0, kills it, and waits on it
    run("L_bash_profile run --qemu --callstatscmds 'sleep 10 & sub_pid=$!; kill -0 $sub_pid; kill $sub_pid; wait $sub_pid 2>/dev/null || true'")


def test_qemu_function_profiling():
    """Test that QEMU profiling works with function definitions and calls.

    This reproduces the bug where 'f() { echo 1; }; f' produces empty results
    because the bash DEBUG trap output doesn't reach the FIFO when using QEMU.
    """
    import json
    import subprocess
    import shlex

    if not is_qemu_available():
        pytest.skip("QEMU not available")

    cmd = shlex.split("L_bash_profile run --json -m qemu 'f() { echo 1; }; f'")
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(proc.stdout)

    # Should have non-zero total time (instructions)
    assert data["total_time"] > 0, f"Expected total_time > 0, got {data['total_time']}"

    # Should have commands recorded
    assert len(data["commands"]) > 0, "Expected commands, got empty list"

    # Should have function 'f' recorded
    func_names = [f["funcname"] for f in data["functions"]]
    assert "f" in func_names, f"Expected function 'f' in {func_names}"

    # Function 'f' should have calls > 0
    f_func = next(f for f in data["functions"] if f["funcname"] == "f")
    assert f_func["calls"] > 0, f"Expected calls > 0 for function 'f', got {f_func['calls']}"
