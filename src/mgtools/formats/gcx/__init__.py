from pathlib import Path

from mgtools.formats.gcx.compiler import GclCompiler
from mgtools.formats.gcx.decompiler import GcxDecompiler
from mgtools.formats.gcx.parser import Gcx


def decompile_gcx(
    input_path: Path,
    output_path: Path,
    dictionary: dict[int, str] | None = None,
):
    # Decompile a GCX file to GCL script text.
    gcx = Gcx.from_file(input_path)
    decomp = GcxDecompiler(gcx, dictionary=dictionary)
    script = decomp.decompile()
    output_path.write_text(script, encoding="utf-8")


def compile_gcx(
    input_path: Path,
    output_path: Path,
):
    # Compile a GCL script back to GCX binary.
    script = input_path.read_text(encoding="utf-8")
    compiled = GclCompiler(script).compile()
    output_path.write_bytes(compiled)
