"""Komut satırı.

dayanak add belge.pdf yonetmelik.docx
dayanak ask "Yıllık izin kaç gün?"
dayanak docs
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .engine import DuplicateDocument, Engine


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(prog="dayanak")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add", help="belge ekle")
    a.add_argument("paths", nargs="+", type=Path)
    q = sub.add_parser("ask", help="soru sor")
    q.add_argument("question")
    q.add_argument("--mode", choices=["auto", "extractive", "llm"], default="auto")
    sub.add_parser("docs", help="belgeleri listele")
    sub.add_parser("samples", help="demo belgelerini yükle")
    args = p.parse_args(argv)

    eng = Engine()
    if args.cmd == "add":
        for path in args.paths:
            try:
                d = eng.add(path.name, path.read_bytes())
                print(f"+ {d.name}: {d.chunks} parça, {d.words} kelime")
            except DuplicateDocument as e:
                print(f"= {e}")
    elif args.cmd == "samples":
        for d in eng.add_samples():
            print(f"+ {d.name}")
    elif args.cmd == "docs":
        for d in eng.store.documents():
            print(f"{d.id:>3}  {d.name}  ({d.chunks} parça)")
    else:
        ans = eng.ask(args.question, mode=args.mode)
        print(f"\n{ans.answer}\n")
        for c in ans.citations:
            used = any(c.n in s.cites for s in ans.sentences)
            if used:
                print(f"[{c.n}] {c.doc_name} — {c.heading or 's.' + str(c.page)}")
        if ans.groundedness is not None:
            print(f"\nDayanak: %{round(ans.groundedness * 100)}  ({ans.mode}, {ans.elapsed_ms} ms)")
        for w in ans.warnings:
            print(f"! {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
