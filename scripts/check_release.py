"""Reject inconsistent release metadata before building or publishing."""
from __future__ import annotations

import argparse
import ast
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def read_version(root: Path = ROOT) -> str:
    module = ast.parse((root / "src/maintainer_radar/__init__.py").read_text(encoding="utf-8"))
    for statement in module.body:
        if isinstance(statement, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "__version__" for target in statement.targets
        ):
            value = ast.literal_eval(statement.value)
            if isinstance(value, str):
                return value
    raise ValueError("The package must define a literal __version__ string")


def validate_release(version: str, changelog: str, tag: str | None = None) -> None:
    # Keep the source/tag spelling identical to the built distribution version.
    # Build backends normalize leading zeros, and Unicode digits are not valid.
    if not re.fullmatch(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)", version):
        raise ValueError(
            f"Expected a canonical stable X.Y.Z package version "
            f"(ASCII digits, no leading zeros), got {version!r}"
        )
    sections = re.split(r"^## (.+)\s*$", changelog, flags=re.MULTILINE)
    entries = list(zip(sections[1::2], sections[2::2]))
    versioned = [(heading, body) for heading, body in entries if heading != "Unreleased"]
    expected = {version, f"Unreleased ({version})"}
    if not versioned or versioned[0][0] not in expected:
        raise ValueError(f"The newest changelog entry must describe package version {version}")
    heading, body = versioned[0]
    if not re.search(r"^- \S", body, re.MULTILINE):
        raise ValueError(f"The changelog entry for {version} needs release notes")
    if tag is not None:
        if any(heading == "Unreleased" and body.strip() for heading, body in entries):
            raise ValueError("Move pending Unreleased notes into the versioned entry before publishing")
        if tag != f"v{version}":
            raise ValueError(f"Release tag {tag!r} does not match package version v{version}")
        if heading != version:
            raise ValueError(f"Finalize the changelog as '## {version}' before publishing {tag}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", help="Published release tag; also requires finalized release notes")
    args = parser.parse_args()
    try:
        version = read_version()
        validate_release(version, (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"), args.tag)
    except ValueError as exc:
        parser.exit(1, f"Release metadata error: {exc}\n")
    print(f"Release metadata consistent: {version}" + (f" ({args.tag})" if args.tag else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
