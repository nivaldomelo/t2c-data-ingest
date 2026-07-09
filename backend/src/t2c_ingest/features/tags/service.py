from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from t2c_ingest.models.tag import JobTag, Tag, slugify


def get_or_create_tag(db: Session, name: str, *, user_id: int | None) -> Tag:
    slug = slugify(name)
    tag = db.scalar(select(Tag).where(Tag.slug == slug))
    if tag:
        return tag
    tag = Tag(name=name.strip(), slug=slug, active=True, created_by=user_id, updated_by=user_id)
    db.add(tag)
    db.flush()
    return tag


def sync_job_tags(db: Session, job_id: int, names: list[str], *, user_id: int | None) -> list[Tag]:
    """Resolve/create tags by name, drop links not present, add new ones. Returns final tags."""
    # Resolve target tags (dedup by slug).
    resolved: dict[int, Tag] = {}
    for raw in names:
        if not raw or not raw.strip():
            continue
        t = get_or_create_tag(db, raw, user_id=user_id)
        resolved[t.id] = t
    target_ids = set(resolved.keys())

    existing = db.scalars(select(JobTag).where(JobTag.job_id == job_id)).all()
    existing_ids = {jt.tag_id for jt in existing}
    for jt in existing:
        if jt.tag_id not in target_ids:
            db.delete(jt)
    for tid in target_ids - existing_ids:
        db.add(JobTag(job_id=job_id, tag_id=tid))
    db.flush()
    return sorted(resolved.values(), key=lambda t: t.name.lower())


def tags_for_jobs(db: Session, job_ids: list[int]) -> dict[int, list[Tag]]:
    if not job_ids:
        return {}
    rows = db.execute(
        select(JobTag.job_id, Tag).join(Tag, Tag.id == JobTag.tag_id).where(JobTag.job_id.in_(job_ids))
    ).all()
    out: dict[int, list[Tag]] = {jid: [] for jid in job_ids}
    for job_id, tag in rows:
        out.setdefault(job_id, []).append(tag)
    for jid in out:
        out[jid].sort(key=lambda t: t.name.lower())
    return out


def job_ids_with_tags(db: Session, slugs: list[str]) -> set[int]:
    """Job ids linked to ANY of the given tag slugs."""
    clean = [slugify(s) for s in slugs if s.strip()]
    if not clean:
        return set()
    rows = db.execute(
        select(JobTag.job_id).join(Tag, Tag.id == JobTag.tag_id).where(Tag.slug.in_(clean))
    ).all()
    return {r[0] for r in rows}


def jobs_count_by_tag(db: Session, tag_ids: list[int]) -> dict[int, int]:
    from sqlalchemy import func

    if not tag_ids:
        return {}
    rows = db.execute(
        select(JobTag.tag_id, func.count(JobTag.id)).where(JobTag.tag_id.in_(tag_ids)).group_by(JobTag.tag_id)
    ).all()
    return {tid: cnt for tid, cnt in rows}
