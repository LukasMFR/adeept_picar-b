#!/usr/bin/env python3
"""Shared configuration loader for the PiCar-B Trixie test scripts.

Loads config/robot.yaml into a plain dict and exposes small, explicit helpers.
Every test script imports from here so hardware settings live in exactly one
place. Errors are raised loudly (SystemExit) rather than swallowed.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

# config/robot.yaml sits next to this file's parent (repo_root/config/robot.yaml)
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "robot.yaml"


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """Load and validate the robot config. Exits with a clear message on failure."""
    cfg_path = Path(path) if path else DEFAULT_CONFIG_PATH
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise SystemExit(
            "PyYAML is not installed. Activate the venv and run:\n"
            "    pip install -r requirements-trixie.txt"
        ) from exc

    if not cfg_path.exists():
        raise SystemExit(f"Config file not found: {cfg_path}")

    with cfg_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

    if not isinstance(data, dict):
        raise SystemExit(f"Config {cfg_path} did not parse to a mapping.")
    return data


def get(cfg: dict[str, Any], *keys: str, default: Any = None) -> Any:
    """Nested lookup: get(cfg, 'motors', 'left', 'enable_pin')."""
    node: Any = cfg
    for key in keys:
        if not isinstance(node, dict) or key not in node:
            return default
        node = node[key]
    return node


def is_dry_run(cfg: dict[str, Any]) -> bool:
    return bool(cfg.get("dry_run", False))


def is_debug(cfg: dict[str, Any]) -> bool:
    return bool(cfg.get("debug", False))


def confirm(prompt: str, expected: str = "yes") -> bool:
    """Require an explicit typed confirmation. Returns True only on exact match."""
    try:
        answer = input(f"{prompt} (type '{expected}' to continue): ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    return answer == expected


if __name__ == "__main__":
    # Quick self-check: print the parsed config.
    import json

    print(json.dumps(load_config(), indent=2, default=str))
