"""Generate secrets.env from .env for Docker Compose.

Compose expands ``$VAR`` when it reads an env file, so a scrypt hash like
``scrypt$16384$8$1$<salt>$<key>`` loses the ``$OXY...`` segment and reaches the container
truncated — 92 chars became 78, and container login failed while local login worked.
``$$`` is Compose's escape for a literal ``$``.

secrets.env is gitignored and holds only the values that contain ``$``. Regenerate after
changing a secret:

    uv run python scripts/write_compose_secrets.py
"""

import sys
from pathlib import Path

ENV = Path(".env")
OUT = Path("secrets.env")


def compose_escape(value: str) -> str:
    """``a$b`` -> ``a$$b``. Compose collapses ``$$`` back to a single ``$``."""
    return value.replace("$", "$$")


def needs_escaping(line: str) -> bool:
    return "=" in line and not line.lstrip().startswith("#") and "$" in line.split("=", 1)[1]


def main() -> int:
    if not ENV.is_file():
        print(".env not found", file=sys.stderr)
        return 1
    lines = [line for line in ENV.read_text().splitlines() if needs_escaping(line)]
    if not lines:
        OUT.write_text("")
        print("no values contain '$'; wrote empty secrets.env")
        return 0
    OUT.write_text("\n".join(compose_escape(line) for line in lines) + "\n")
    keys = [line.split("=", 1)[0] for line in lines]
    print(f"wrote {OUT} with {len(lines)} escaped value(s): {', '.join(keys)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
