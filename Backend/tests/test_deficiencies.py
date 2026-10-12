from src.deficiencies import analyze_deficiencies, classify_chunk, classify_text


def test_open_status_is_an_active_deficiency():
    text = "Finding B-1 Rebar\nBars were at 175 mm. Status: open. Action: add bars."
    assert classify_text(text) == "open"


def test_closed_status_is_not_an_active_deficiency():
    text = "Finding B-2 Cover\nCover was 46 mm and meets the clause. Status: closed."
    assert classify_text(text) == "closed"
    report = analyze_deficiencies([
        {
            "doc_type": "inspection_report",
            "section": "Finding B-2 Cover",
            "quote": text,
            "text": text,
            "file_name": "report.pdf",
            "page_number": 2,
        }
    ])
    assert report.has_deficiency is False
    assert report.text is None


def test_defect_language_without_status_requires_verification():
    text = "Finding C-1 Joint\nDEFICIENCY noted at the joint."
    assert classify_text(text) == "unverified"
    report = analyze_deficiencies([
        {
            "doc_type": "inspection_report",
            "section": "Finding C-1 Joint",
            "quote": text,
            "text": text,
            "file_name": "report.pdf",
            "page_number": 3,
        }
    ])
    assert report.has_deficiency is False
    assert report.status == "requires_verification"
    assert report.text.startswith("REQUIRES VERIFICATION")


def test_closed_and_open_findings_in_one_excerpt_keep_the_open_one():
    text = (
        "Finding A-1 Old item\nCorrected before this visit. Status: closed.\n"
        "Finding A-2 Current item\nThe bar spacing does not comply. Status: open."
    )
    assert classify_text(text) == "open"


def test_building_code_text_is_not_a_deficiency():
    chunk = {"doc_type": "building_code", "text": "Status: open. This does not comply.", "quote": "Status: open"}
    assert classify_chunk(chunk) == "none"
