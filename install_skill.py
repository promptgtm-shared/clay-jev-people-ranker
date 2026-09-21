from __future__ import annotations

import argparse
import shutil
from pathlib import Path


SKILL_NAME = "clay-jev-people-ranker"
USER_ROOTS = {
    "claude-code": Path.home() / ".claude" / "skills",
    "cursor": Path.home() / ".cursor" / "skills",
    "grok-build": Path.home() / ".grok" / "skills",
}
PROJECT_ROOTS = {
    "claude-code": Path(".claude") / "skills",
    "cursor": Path(".cursor") / "skills",
    "grok-build": Path(".grok") / "skills",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Install the Clay + JEV skill for supported local coding agents."
    )
    parser.add_argument(
        "--agent",
        choices=["claude-code", "cursor", "grok-build", "all"],
        required=True,
    )
    parser.add_argument("--scope", choices=["user", "project"], default="user")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="Project root used with --scope project; defaults to the current directory.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Merge into an existing skill directory and overwrite matching files.",
    )
    return parser.parse_args()


def destinations(args: argparse.Namespace) -> list[Path]:
    agents = list(USER_ROOTS) if args.agent == "all" else [args.agent]
    if args.scope == "user":
        return [USER_ROOTS[agent] / SKILL_NAME for agent in agents]
    project_root = args.project_root.expanduser().resolve()
    return [project_root / PROJECT_ROOTS[agent] / SKILL_NAME for agent in agents]


def main() -> int:
    args = parse_args()
    source = Path(__file__).resolve().parent
    targets = destinations(args)

    conflicts = [target for target in targets if target.exists() and target != source]
    if conflicts and not args.force:
        formatted = "\n".join(f"- {target}" for target in conflicts)
        raise RuntimeError(
            "The skill already exists at the following destination(s):\n"
            f"{formatted}\nRe-run with --force to update matching files."
        )

    ignore = shutil.ignore_patterns(
        ".env",
        "*.zip",
        "*.pyc",
        "__pycache__",
        ".git",
        "outputs",
    )
    for target in targets:
        if target == source:
            print(f"Already installed: {target}")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, target, dirs_exist_ok=args.force, ignore=ignore)
        print(f"Installed {SKILL_NAME}: {target}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        raise SystemExit(f"Error: {exc}") from exc
