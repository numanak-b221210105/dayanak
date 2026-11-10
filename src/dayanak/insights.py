"""Kullanım içgörüleri: sorulan sorulardan, bilgi bankasının nerede yetersiz
kaldığını ve cevapların ne kadar güvenilir olduğunu çıkarır.

En değerli çıktı "gaps" listesidir: belgelerde dayanağı bulunamayan sorular.
Bir şirket için bu, hangi konuda doküman yazılması gerektiğinin doğrudan
göstergesidir.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from .schema import DayCount, DocCount, Gap, Insights, QueryLog
from .store import Store
from .text import tr_lower


def _norm(q: str) -> str:
    return " ".join(tr_lower(q).replace("?", " ").split())


def compute(store: Store, days: int = 14) -> Insights:
    rows = store.queries()
    total = len(rows)
    abstained = sum(r["abstained"] for r in rows)
    grounded = [r["groundedness"] for r in rows if r["groundedness"] is not None]

    tz = datetime.now().astimezone().tzinfo  # kullanıcının yerel saat dilimi
    today = datetime.now(tz).date()
    per_day = Counter(datetime.fromtimestamp(r["ts"], tz).date().isoformat() for r in rows)
    by_day = [
        DayCount(date=(d := (today - timedelta(days=i)).isoformat()), count=per_day.get(d, 0))
        for i in range(days - 1, -1, -1)
    ]

    names = {d.id: d.name for d in store.documents()}
    doc_counts: Counter[int] = Counter()
    for r in rows:
        doc_counts.update(d for d in json.loads(r["cited_docs"]) if d in names)
    top_docs = [DocCount(doc_id=d, name=names[d], count=c) for d, c in doc_counts.most_common(6)]

    gap_groups: dict[str, list] = defaultdict(list)
    for r in rows:
        if r["abstained"]:
            gap_groups[_norm(r["question"])].append(r)
    gaps = sorted(
        (Gap(question=g[0]["question"], count=len(g), last_ts=max(x["ts"] for x in g)) for g in gap_groups.values()),
        key=lambda g: (-g.count, -g.last_ts),
    )[:10]

    recent = [
        QueryLog(
            id=r["id"],
            ts=r["ts"],
            question=r["question"],
            mode=r["mode"],
            abstained=bool(r["abstained"]),
            groundedness=r["groundedness"],
            elapsed_ms=r["elapsed_ms"],
            feedback=r["feedback"],
        )
        for r in rows[:12]
    ]
    return Insights(
        total=total,
        answered=total - abstained,
        abstained=abstained,
        abstain_rate=round(abstained / total, 3) if total else None,
        avg_groundedness=round(sum(grounded) / len(grounded), 3) if grounded else None,
        avg_ms=round(sum(r["elapsed_ms"] for r in rows) / total, 1) if total else None,
        feedback_up=sum(1 for r in rows if r["feedback"] == 1),
        feedback_down=sum(1 for r in rows if r["feedback"] == -1),
        by_day=by_day,
        top_docs=top_docs,
        gaps=gaps,
        recent=recent,
    )


__all__ = ["compute"]
