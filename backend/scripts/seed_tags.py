"""Seed initial useful tags (idempotent by slug). Run:
    docker compose exec api python scripts/seed_tags.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sqlalchemy import select  # noqa: E402

from t2c_ingest.core.db import SessionLocal  # noqa: E402
from t2c_ingest.models.tag import Tag, slugify  # noqa: E402

TAGS = ["spark", "python", "mysql", "postgres", "incremental", "full", "massa_teste",
        "bronze", "silver", "gold", "pipeline", "teste", "produção"]


def main() -> None:
    created = 0
    with SessionLocal() as db:
        for name in TAGS:
            slug = slugify(name)
            if db.scalar(select(Tag).where(Tag.slug == slug)):
                continue
            db.add(Tag(name=name, slug=slug, active=True, created_by=None, updated_by=None))
            created += 1
        db.commit()
    print(f"Tags seed: {created} criada(s), {len(TAGS) - created} já existente(s).")


if __name__ == "__main__":
    main()
