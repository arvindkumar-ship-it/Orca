import re
from sqlalchemy import text
from sqlalchemy.orm import Session


def _interpolate(s: str, v: dict) -> str:
    return re.sub(r"\{\{(\w+)\}\}", lambda m: str(v.get(m.group(1), "")), s)


def render_template(db: Session, template_key: str, locale: str, v: dict) -> dict:
    row = db.execute(text("""
        SELECT title_template, body_template FROM notification_templates WHERE template_key = :k AND locale = :l
        UNION ALL
        SELECT title_template, body_template FROM notification_templates WHERE template_key = :k AND locale = 'en'
        LIMIT 1
    """), {"k": template_key, "l": locale}).mappings().first()
    if not row:
        return {"title": "Safety Alert", "body": _interpolate("Danger near {{beach_name}}. Move to safe zone now.", v)}
    return {"title": _interpolate(row["title_template"], v), "body": _interpolate(row["body_template"], v)}
