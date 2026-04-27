"""
Universal Eyeglass Socket — Headless CAD export

Exports STEP and STL files for all standard sizes.
Run from the project root:

    python src/ues/export.py build/cad

Outputs (one set per circular size code):
    ues-{size}-frame.step
    ues-{size}-lens.step
    ues-{size}-frame.stl
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

# Allow `import ues` from any working directory
sys.path.insert(0, str(Path(__file__).parent.parent))

from build123d import export_step, export_stl

from ues.spec.lens import LENS_SPECS
from ues.to_build123d.lens import create_reference_lens
from ues.to_build123d.frame import create_frame


def export_size(size_code: str, out_dir: Path) -> None:
    print(f"  Building {size_code} frame …", flush=True)
    frame = create_frame(size_code)
    export_step(frame, str(out_dir / f"ues-{size_code}-frame.step"))
    export_stl(frame, str(out_dir / f"ues-{size_code}-frame.stl"))

    print(f"  Building {size_code} lens …", flush=True)
    lens = create_reference_lens(size_code)
    export_step(lens, str(out_dir / f"ues-{size_code}-lens.step"))

    print(f"  ✓ {size_code}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export UES CAD to STEP/STL")
    parser.add_argument("outdir", nargs="?", default="build/cad",
                        help="Output directory (default: build/cad)")
    args = parser.parse_args()

    out_dir = Path(args.outdir)
    out_dir.mkdir(parents=True, exist_ok=True)

    sizes = [code for code in LENS_SPECS if code.startswith("UES-C-")]
    print(f"Exporting {len(sizes)} circular sizes to {out_dir}/")
    for size_code in sizes:
        export_size(size_code, out_dir)

    print("Done.")


if __name__ == "__main__":
    main()
