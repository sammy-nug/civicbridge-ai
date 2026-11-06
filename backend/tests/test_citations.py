from datetime import date

from app.services.citations import (
    build_citations, cited_passages, extract_passage, remove_today_mentions, spelled_numbers_to_digits,
    strip_links, uncited_ratio, unsupported_numbers,
)
from app.services.retrieval import Evidence


def evidence(chunk="a", doc="doc-a", page=1, text="Apply not less than 90 days before polling day.", status="current"):
    return Evidence(
        chunk_id=chunk, text=text, similarity=0.7, rank_score=0.7, document_id=doc, title=f"Title {doc}",
        organisation="INEC", url=f"https://example.org/{doc}.pdf", status=status, publication_date="2026",
        publication_date_basis="Title", retrieved_date="2026-11-05", page=page, section="Section 18",
        extraction="digital", superseded_by=None,
    )


def test_invented_marker_is_removed_and_gets_no_citation():
    (text,), cited = build_citations(["A fact [1]. Another [7]."], [evidence()], "apply")
    assert text == "A fact [1]. Another ."
    assert [c.number for c in cited] == [1]


def test_only_invented_markers_means_no_citations():
    _, cited = build_citations(["A fact [9]."], [evidence()], "apply")
    assert cited == []


def test_citation_fields_come_from_metadata_only():
    _, cited = build_citations(["A fact [1]."], [evidence()], "apply")
    assert cited[0].url == "https://example.org/doc-a.pdf"
    assert cited[0].title == "Title doc-a"
    assert cited[0].page == 1


def test_same_page_is_merged_and_numbers_are_renumbered():
    items = [evidence("x", "other", 3), evidence("a", "doc-a", 1), evidence("b", "doc-a", 1)]
    (text,), cited = build_citations(["First [2]. Second [3]. Third [1]."], items, "q")
    assert text == "First [1]. Second [1]. Third [2]."
    assert [c.document_id for c in cited] == ["doc-a", "other"]


def test_older_documents_carry_a_warning():
    _, cited = build_citations(["Fact [1]."], [evidence(status="superseded")], "q")
    assert any("newer" in note for note in cited[0].notes)


def test_number_not_in_evidence_is_caught():
    assert unsupported_numbers("Apply 60 days before [1].", [evidence()]) == ["60"]
    assert unsupported_numbers("Apply 90 days before [1].", [evidence()]) == []


def test_list_numbering_and_markers_are_not_counted_as_facts():
    assert unsupported_numbers("1. Apply 90 days before [1].\n2. Go in person [1].", [evidence()]) == []


def test_uncited_ratio():
    assert uncited_ratio("This sentence has a source [1]. So does this other one [1].") == 0
    assert uncited_ratio("This sentence has a source [1]. This other sentence has nothing at all.") == 0.5
    assert uncited_ratio("In general, a calendar helps you plan ahead for things.") == 0


def test_llm_written_links_are_stripped():
    assert "http" not in strip_links("See https://fake-inec.example/form for details [1].")


def test_passage_prefers_matching_sentence():
    text = "The Commission has a fund. A lost voter card must be replaced in person. The fund is audited."
    assert "lost voter card" in extract_passage(text, "replace lost voter card")


def test_numbers_touching_letters_in_ocr_text_still_count():
    item = evidence(text="Between8:00amand8:30am the officer shall open the box.")
    assert unsupported_numbers("It opens at 8:30 [1].", [item]) == []


def test_todays_full_date_is_allowed_but_not_its_parts():
    today = date(2026, 11, 6)
    for mention in ("6 November 2026", "November 6, 2026", "2026-11-06", "6th of November 2026"):
        text = remove_today_mentions(f"As of {mention} the deadline has passed [1].", today)
        assert unsupported_numbers(text, [evidence()]) == []
    invented = remove_today_mentions("Apply 6 days before polling day [1].", today)
    assert unsupported_numbers(invented, [evidence()]) == ["6"]


def test_spelled_out_numbers_are_checked():
    assert unsupported_numbers("Apply seven days before polling day [1].", [evidence()]) == ["7"]
    assert unsupported_numbers("Apply ninety days before polling day [1].", [evidence()]) == []
    worded = evidence(text="A fine of not less than five million naira, within twenty-one days.")
    assert unsupported_numbers("The fine is at least 5,000,000 naira, within 21 days [1].", [worded]) == []
    assert unsupported_numbers("The fine is at least five hundred thousand naira [1].", [worded]) == ["500000"]


def test_spelled_number_conversion():
    assert spelled_numbers_to_digits("one of the two hundred and fifty units") == "one of the 250 units"
    assert spelled_numbers_to_digits("two and three") == "2 and 3"
    assert spelled_numbers_to_digits("someone weighs ninety") == "someone weighs 90"


def test_general_sentences_with_electoral_facts_count_as_uncited():
    assert uncited_ratio("You must apply in person at the office [1]. In general, you can vote at any polling unit.") == 0.5
    assert uncited_ratio("You must apply in person at the office [1]. In general, keep your documents somewhere safe.") == 0


def test_cited_passages_are_limited_to_the_cited_page():
    cited_page, other_page = evidence(chunk="a", page=1), evidence(chunk="b", page=2, text="The fine is 500,000 naira.")
    _, citations = build_citations(["Apply 90 days before [1]."], [cited_page, other_page], "replace")
    assert cited_passages([cited_page, other_page], citations) == [cited_page]
