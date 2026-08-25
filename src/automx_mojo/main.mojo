from std.python import Python, PythonObject
from std.sys import argv, exit


def main() raises:
    """Run the existing automx Python CLI through Mojo's CPython interop."""
    var bridge = Python.import_module("automx.mojo_entrypoint")
    var sys = Python.import_module("sys")
    var args = Python.list()
    var mojo_args = argv()

    # Embedded CPython does not inherit the native executable's argv. argparse
    # expects only the arguments after the executable name when argv is passed.
    for index in range(1, len(mojo_args)):
        _ = args.append(PythonObject(String(mojo_args[index])))

    var status = Int(py=bridge.run(args))

    # std.sys.exit() terminates without finalizing CPython, so flush both
    # streams explicitly before preserving the Python CLI's exit status.
    _ = sys.stdout.flush()
    _ = sys.stderr.flush()
    if status != 0:
        exit(status)
