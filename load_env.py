"""
load_env.py — Load .env file and run the test pipeline.

Usage (replaces typing env vars every session):
    python load_env.py text
    python load_env.py animated
    python load_env.py both

This reads your .env file, sets all environment variables for the session,
then hands off to test_local.py automatically.
"""

import os, sys, subprocess
from pathlib import Path

ENV_FILE = Path(__file__).parent / ".env"


def load_env(path: Path) -> dict:
    """Parse .env file — ignores comments and blank lines."""
    if not path.exists():
        raise SystemExit(
            f"ERROR: .env file not found at {path}\n"
            "Create it by copying .env and filling in your values."
        )

    loaded = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key   = key.strip()
        value = value.strip()
        # Strip surrounding quotes if present
        if len(value) >= 2 and value[0] in ('"', "'") and value[-1] == value[0]:
            value = value[1:-1]
        if value and value != f"your_{key.lower()}_here" and not value.startswith("paste_"):
            loaded[key] = value
        else:
            print(f"WARN: {key} not set in .env — skipping")
    return loaded


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "text"

    print(f"Loading environment from {ENV_FILE}")
    env_vars = load_env(ENV_FILE)

    if not env_vars:
        raise SystemExit("ERROR: No valid variables found in .env — check the file.")

    # Merge into current environment; force unbuffered output for real-time logging
    env = {**os.environ, **env_vars, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"}

    # Mirror CHANNEL1_CONFIG → CHANNEL_CONFIG (same alias daemon uses)
    if "CHANNEL1_CONFIG" in env and "CHANNEL_CONFIG" not in env:
        env["CHANNEL_CONFIG"] = env["CHANNEL1_CONFIG"]

    missing = [k for k in ["GEMINI_API_KEY", "PEXELS_API_KEY", "CHANNEL_CONFIG"]
               if k not in env]
    if missing:
        raise SystemExit(
            f"ERROR: Missing required variables: {', '.join(missing)}\n"
            f"Edit your .env file and fill them in."
        )

    print(f"[OK] Loaded: GEMINI_API_KEY={'*' * 8}, PEXELS_API_KEY={'*' * 8}, CHANNEL_CONFIG=set")
    print(f"[Test] Running: python test_local.py {mode}\n")

    result = subprocess.run(
        [sys.executable, "test_local.py", mode],
        env=env,
    )
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
