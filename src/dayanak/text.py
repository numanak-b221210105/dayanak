"""Türkçe metin işleme: küçük harf, kök alma, cümle bölme.

Kök alma için "önek kesme" (Fn) yöntemi kullanılır: her kelimenin ilk n harfi
alınır. Türkçe gibi eklemeli dillerde bu basit yöntemin, karmaşık morfolojik
çözümleyicilere yakın arama başarısı verdiği bilgi erişimi literatüründe
gösterilmiştir (Can vd., 2008). Bağımlılık gerektirmez ve çok hızlıdır.

n=4, 5 ve 6 evals/ altındaki sorularla karşılaştırıldı; n=6 hem doğru belgeyi
ilk sırada bulmada hem de cevabı belgelerde olmayan soruları ayırt etmede en
iyi sonucu verdi (ör. n=5'te "yemekhane" ile "yemek" aynı köke düşüyor).
"""

from __future__ import annotations

import re

STEM_LEN = 6

# Arama kalitesini düşüren çok sık kelimeler (bilinçli olarak kısa tutuldu)
STOPWORDS = frozenset(
    """
    acaba ama ancak artık aslında az bazı belki ben beni benim bile bir biri birkaç birşey biz bize bizi
    bu buna bunda bundan bunu bunun burada çok çünkü da daha de defa diye dolayı en gibi göre hem hep
    hepsi her hiç için ile ise kadar ki kim mi mu mü mı nasıl ne neden nerede nereye niye o olan olarak
    oldu olduğu olmak olur on ona ondan onlar onu onun orada sanki sen siz şey şu şuna şunu tüm ve veya
    ya yani yoksa zaten değil midir mıdır nedir hangi kaç ayrıca ilgili üzere sonra önce olması
    the a an and or of to in is are be for on with by as at it this that what which how
    """.split()
)

_WORD = re.compile(r"[0-9]+(?:[.,][0-9]+)*|[a-zçğıöşüâîû]+", re.IGNORECASE)
_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
_SENT = re.compile(r"(?<=[.!?…])\s+(?=[A-ZÇĞİÖŞÜ0-9\"'(\[])|\n{2,}|\n(?=[-•*]\s)")


def tr_lower(s: str) -> str:
    """'İSTANBUL' -> 'istanbul', 'IŞIK' -> 'ışık'. (str.lower() Türkçe I/İ'yi bozar.)"""
    return s.replace("I", "ı").replace("İ", "i").lower()


def words(text: str) -> list[str]:
    return _WORD.findall(tr_lower(text))


def stem(word: str) -> str:
    return word if word[0].isdigit() else word[:STEM_LEN]


def terms(text: str) -> list[str]:
    """Arama terimleri: küçük harf, durak kelimeler atılmış, F5 kökleri."""
    return [stem(w) for w in words(text) if w not in STOPWORDS and (len(w) > 1 or w.isdigit())]


def numbers(text: str) -> set[str]:
    """Metindeki sayılar, biçimden bağımsız: '10.000' ve '10000' aynı kabul edilir."""
    out = set()
    for n in _NUMBER.findall(text):
        digits = re.sub(r"[.,](?=\d{3}\b)", "", n).replace(",", ".")
        out.add(digits.rstrip("0").rstrip(".") if "." in digits else digits)
    return out


def sentences(text: str) -> list[str]:
    parts = _SENT.split(text.strip())
    out = []
    for p in parts:
        p = re.sub(r"\s+", " ", p).strip(" -•*#\t")
        if len(p) > 2:
            out.append(p)
    return out
