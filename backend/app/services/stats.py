"""Dashboard statistics computed ONLY from scans saved on this device.

An empty database returns zeros and empty lists, never sample numbers.
"""

from __future__ import annotations

from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import Feedback, Scan


def compute_stats(session: Session) -> dict:
    """Counts by disease, ISO week and district, plus feedback totals."""
    rows = session.execute(
        select(Scan.class_id, Scan.crop, Scan.disease, Scan.created_at, Scan.district)
    ).all()
    feedback_rows = session.execute(select(Feedback.correct)).all()

    labels: dict[str, str] = {}
    by_disease: Counter[str] = Counter()
    by_week: Counter[str] = Counter()
    by_district: Counter[str] = Counter()
    healthy = 0
    for class_id, crop, disease, created_at, district in rows:
        labels[class_id] = f"{disease} ({crop})"
        by_disease[class_id] += 1
        iso_year, iso_week, _ = created_at.isocalendar()
        by_week[f"{iso_year}-W{iso_week:02d}"] += 1
        by_district[district or "Unspecified"] += 1
        if "healthy" in class_id.lower():
            healthy += 1

    correct = sum(1 for (value,) in feedback_rows if value)
    return {
        "total_scans": len(rows),
        "healthy_scans": healthy,
        "diseased_scans": len(rows) - healthy,
        "by_disease": [
            {"key": key, "label": labels[key], "count": count} for key, count in by_disease.most_common()
        ],
        "by_week": [{"key": key, "label": key, "count": by_week[key]} for key in sorted(by_week)],
        "by_district": [
            {"key": key, "label": key, "count": count} for key, count in by_district.most_common()
        ],
        "feedback": {
            "total": len(feedback_rows),
            "correct": correct,
            "incorrect": len(feedback_rows) - correct,
        },
    }
