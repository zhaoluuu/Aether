from __future__ import annotations

import argparse
import os
from pathlib import Path

import bcrypt
from sqlalchemy import create_engine, text


def load_env(env_path: Path) -> None:
    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key, value)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default="/opt/aether/current/.env")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    args = parser.parse_args()

    load_env(Path(args.env))
    database_url = os.environ["DATABASE_URL"]
    password_hash = bcrypt.hashpw(args.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    engine = create_engine(database_url)
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                update users
                set password_hash = :password_hash,
                    updated_at = now()
                where email = :email
                returning email, username, role, is_active
                """
            ),
            {"password_hash": password_hash, "email": args.email},
        ).mappings().first()

    if row is None:
        raise SystemExit(f"user not found: {args.email}")

    print(dict(row))


if __name__ == "__main__":
    main()
