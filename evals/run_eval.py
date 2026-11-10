"""Dayanak'ı örnek belgeler üzerinde ölçer.

Metrikler
  hit@1 / hit@3 : doğru belge ilk 1 / 3 sonuçta mı (arama kalitesi)
  MRR           : doğru belgenin ortalama ters sırası
  fact recall   : beklenen bilgi (ör. "20", "1 saat") cevapta geçiyor mu
  abstain       : cevabı belgelerde olmayan sorularda "bulamadım" deme oranı
  false abstain : cevabı olan soruda yanlışlıkla "bulamadım" deme oranı
  groundedness  : cevap cümlelerinin dayanağı doğrulanma oranı

Kullanım:
  python evals/run_eval.py                 # alıntı tabanlı, LLM gerekmez
  python evals/run_eval.py --mode llm      # LLM ayarları için README'ye bakın
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dayanak.config import settings
from dayanak.engine import Engine

QUESTIONS = Path(__file__).parent / "questions.jsonl"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["extractive", "llm", "auto"], default="extractive")
    p.add_argument("--embed", action="store_true", help="vektör aramasını da kullan (embedding servisi gerekir)")
    args = p.parse_args()

    rows = [json.loads(line) for line in QUESTIONS.read_text("utf-8").splitlines() if line.strip()]
    with tempfile.TemporaryDirectory() as tmp:
        cfg = settings().__class__(**{**settings().__dict__, "data_dir": Path(tmp)})
        eng = Engine(cfg)
        for f in sorted((Path(__file__).parents[1] / "samples").glob("*.md")):
            eng.add(f.name, f.read_bytes(), embed=args.embed)

        answerable = [r for r in rows if r["doc"]]
        unanswerable = [r for r in rows if not r["doc"]]
        h1 = h3 = rr = fact = false_abs = 0
        grounded: list[float] = []
        t0 = time.perf_counter()
        print(f"\nMod: {args.mode}\n")
        for r in answerable:
            hits = eng.search(r["q"], k=5)
            names = [h.chunk.doc_name for h in hits]
            pos = names.index(r["doc"]) + 1 if r["doc"] in names else 0
            h1 += pos == 1
            h3 += 0 < pos <= 3
            rr += 1 / pos if pos else 0
            a = eng.ask(r["q"], mode=args.mode)
            ok = all(f.lower() in a.answer.lower() for f in r["facts"])
            fact += ok
            false_abs += a.abstained
            if a.groundedness is not None:
                grounded.append(a.groundedness)
            mark = "✓" if ok else ("∅" if a.abstained else "✗")
            print(f" {mark} {r['q'][:58]:<58} #{pos or '-'}  {a.answer[:70]}")
        abst = 0
        for r in unanswerable:
            a = eng.ask(r["q"], mode=args.mode)
            abst += a.abstained
            print(f" {'∅' if a.abstained else '!'} {r['q'][:58]:<58}     {a.answer[:70]}")
        n = len(answerable)
        print(f"\nhit@1          {h1 / n:.0%}")
        print(f"hit@3          {h3 / n:.0%}")
        print(f"MRR            {rr / n:.2f}")
        print(f"fact recall    {fact / n:.0%}")
        print(f"false abstain  {false_abs / n:.0%}")
        print(f"abstain (n/a)  {abst / len(unanswerable):.0%}")
        if grounded:
            print(f"groundedness   {sum(grounded) / len(grounded):.0%}")
        print(f"süre           {time.perf_counter() - t0:.1f} sn")
    return 0


if __name__ == "__main__":
    sys.exit(main())
