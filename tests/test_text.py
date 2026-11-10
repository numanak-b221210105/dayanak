import pytest

from dayanak.chunking import chunk_pages
from dayanak.text import numbers, sentences, terms, tr_lower


def test_turkish_lowercase():
    assert tr_lower("İSTANBUL IŞIK") == "istanbul ışık"


def test_terms_drop_stopwords_and_stem():
    t = terms("Yıllık izin kaç gündür ve nasıl alınır?")
    assert "kaç" not in t and "ve" not in t
    assert "yıllık" in t and "izin" in t


@pytest.mark.parametrize(
    "text, expected",
    [("10.000 TL", {"10000"}), ("%30 ve 4.500", {"30", "4500"}), ("9,5 km", {"9.5"}), ("60 gün", {"60"})],
)
def test_numbers_are_normalised(text, expected):
    assert numbers(text) == expected


def test_sentences_split_bullets():
    s = sentences("Liste:\n- Evlenme: 3 iş günü\n- Taşınma: 1 iş günü")
    assert "Evlenme: 3 iş günü" in s and "Taşınma: 1 iş günü" in s


def test_chunks_keep_headings_and_do_not_split_sections():
    text = "# Başlık A\n\n" + ("Kelime " * 50 + ".\n\n") * 3 + "# Başlık B\n\nKısa paragraf."
    chunks = chunk_pages([(1, text)])
    assert {c.heading for c in chunks} == {"Başlık A", "Başlık B"}
    assert all(len(c.text.split()) <= 200 for c in chunks)
    assert chunks[-1].text == "Kısa paragraf."  # bölümler arası örtüşme taşınmaz
