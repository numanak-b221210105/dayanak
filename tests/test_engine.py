import pytest

from dayanak.engine import DuplicateDocument
from dayanak.verify import ABSTAIN_PHRASE

from .conftest import SAMPLES


def test_duplicate_upload_is_rejected(engine):
    f = SAMPLES / "izin-politikasi.md"
    with pytest.raises(DuplicateDocument):
        engine.add(f.name, f.read_bytes(), embed=False)


def test_search_finds_right_document(engine):
    hits = engine.search("Parola en az kaç karakter olmalı?", k=3)
    assert hits[0].chunk.doc_name == "bilgi-guvenligi-politikasi.md"


def test_extractive_answer_is_fully_grounded(engine):
    a = engine.ask("İş seyahatinde günlük yemek limiti ne kadar?", mode="extractive")
    assert "750" in a.answer
    assert a.groundedness == 1.0 and not a.abstained
    assert a.citations[0].doc_name == "masraf-yonetmeligi.md"


def test_out_of_scope_question_abstains(engine):
    a = engine.ask("Şirket servis güzergahları hangileri?", mode="extractive")
    assert a.abstained and a.answer == ABSTAIN_PHRASE and a.citations == []


def test_llm_answer_with_correct_citation_passes(engine_with_llm):
    eng = engine_with_llm("Parolalar en az 12 karakterden oluşur [1]. Parolalar 90 günde bir değiştirilir [1].")
    a = eng.ask("Parola kuralları nelerdir?", mode="llm")
    assert a.mode == "llm"
    assert a.groundedness == 1.0
    call = eng.llm_client.calls[0]
    assert "[1]" in call["messages"][1]["content"]  # kaynaklar numaralı verildi


def test_hallucinated_number_is_flagged(engine_with_llm):
    """Kaynakta 12 yazıyor; model 16 derse cümle işaretlenmeli."""
    eng = engine_with_llm("Parolalar en az 16 karakterden oluşur [1].")
    a = eng.ask("Parola en az kaç karakter olmalı?", mode="llm")
    s = a.sentences[0]
    assert not s.supported and s.missing_numbers == ["16"]
    assert a.groundedness == 0.0


def test_uncited_and_invalid_citations_are_flagged(engine_with_llm):
    eng = engine_with_llm("Parolalar 90 günde bir değiştirilir. MFA zorunludur [9].")
    a = eng.ask("Parolalar ne sıklıkla değiştirilir?", mode="llm")
    assert [s.supported for s in a.sentences] == [False, False]
    assert a.sentences[0].reason == "Kaynak gösterilmemiş"
    assert any("[9]" in w for w in a.warnings)


def test_llm_abstention_is_respected(engine_with_llm):
    eng = engine_with_llm(ABSTAIN_PHRASE)
    a = eng.ask("Yıllık izin talebi kaç gün önceden yapılmalı?", mode="llm")
    assert a.abstained and a.groundedness is None


def test_auto_falls_back_to_quotes_without_llm(engine):
    a = engine.ask("Babalık izni kaç gün?", mode="auto")
    assert a.mode == "extractive" and "5" in a.answer


def test_llm_error_falls_back_to_quotes(engine):
    a = engine.ask("Babalık izni kaç gün?", mode="llm")  # LLM adresi kapalı port
    assert a.mode == "extractive" and "5 iş günü" in a.answer
    assert any("LLM kullanılamadı" in w for w in a.warnings)


def test_delete_updates_index(engine):
    doc = next(d for d in engine.store.documents() if d.name == "masraf-yonetmeligi.md")
    engine.store.delete(doc.id)
    a = engine.ask("İş seyahatinde günlük yemek limiti ne kadar?", mode="extractive")
    assert all(c.doc_name != "masraf-yonetmeligi.md" for c in a.citations)
