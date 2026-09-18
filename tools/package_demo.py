"""Compatibility entry point for the separate demo distribution."""

import argparse
from pathlib import Path
from package_release import ROOT, package

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "dist/RoleWeaver-Demo-Alpha-0.1.0.tar.gz"
    )
    args = parser.parse_args()
    package(args.output, "demo")
    print(args.output)
