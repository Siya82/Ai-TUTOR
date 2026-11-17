"""
Tests for app/services/epub.py (ADR-032 ePub addendum) and the licence
gate in scripts/ingest_books.py. Builds small ePubs in memory -- no DB.
"""

import zipfile

import pytest

from app.services.epub import detect_licence, licence_family, parse_epub, read_asset
from scripts.ingest_books import licence_decision

CONTAINER = """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>"""

OPF = """<?xml version="1.0"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>Everything Maths Grade 10</dc:title>
    <dc:rights>{rights}</dc:rights>
  </metadata>
  <manifest>
    <item id="front" href="front.xhtml" media-type="application/xhtml+xml"/>
    <item id="ch1" href="text/chapter%201.xhtml" media-type="application/xhtml+xml"/>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml"/>
    <item id="img" href="images/graph.png" media-type="image/png"/>
    <item id="js" href="evil.js" media-type="text/javascript"/>
  </manifest>
  <spine>
    <itemref idref="front"/>
    <itemref idref="nav" linear="no"/>
    <itemref idref="ch1"/>
  </spine>
</package>"""

FRONT = """<html xmlns="http://www.w3.org/1999/xhtml"><head><title>x</title><style>p{color:red}</style></head>
<body><h1>About this book</h1>
<p>You are free to share and adapt this book. This work is licensed under a
Creative Commons Attribution 4.0 International License (CC BY 4.0). Written by Siyavula and volunteers,
who spent many hours of their time putting this textbook together for learners across South Africa.
You can read it online, download it to your phone, or print it, and you may copy any part of it.</p>
</body></html>"""

CHAPTER = """<html xmlns="http://www.w3.org/1999/xhtml"><body>
<section class="chapter"><h1><span class="num">2</span> Exponents</h1>
<p>Exponents are a short way of writing repeated multiplication. In this chapter we look at the
laws of exponents and how they are used to simplify expressions. Read each worked example carefully
before you try the exercises at the end of each section. Long enough to stand alone as its own section.</p>
<div class="section"><h2>Laws of exponents</h2>
<p onclick="alert(1)">For any real number <math><semantics><mrow><msup><mi>a</mi><mi>m</mi></msup></mrow>
<annotation encoding="application/x-tex">a^m \\times a^n = a^{m+n}</annotation></semantics></math> holds.
The base stays the same and the exponents are added together, which is the first law of exponents.
This law is used everywhere in algebra, so make sure you understand why it works before moving on.</p>
<img src="../images/graph.png" alt="Graph of y = 2^x"/>
<img src="https://tracker.example.com/pixel.png" alt="tracker"/>
<script>steal()</script>
<a href="javascript:steal()">click</a>
<table><tr><td colspan="2" style="color:red">Law</td></tr></table>
</div></section>
<h2>Tiny</h2><p>Short.</p>
</body></html>"""


def _epub(tmp_path, rights="CC BY 4.0", front=FRONT):
    path = tmp_path / "book.epub"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("mimetype", "application/epub+zip")
        zf.writestr("META-INF/container.xml", CONTAINER)
        zf.writestr("OEBPS/content.opf", OPF.format(rights=rights))
        zf.writestr("OEBPS/front.xhtml", front)
        zf.writestr("OEBPS/nav.xhtml", "<html><body><h1>Contents</h1><p>nav</p></body></html>")
        zf.writestr("OEBPS/text/chapter 1.xhtml", CHAPTER)
        zf.writestr("OEBPS/images/graph.png", b"\x89PNG fake")
        zf.writestr("OEBPS/evil.js", "steal()")
    return path


def test_parse_splits_at_headings_and_follows_spine(tmp_path):
    book = parse_epub(_epub(tmp_path))
    assert book.title == "Everything Maths Grade 10"
    titles = [s.title for s in book.sections]
    assert titles[0] == "About this book"
    assert "2 Exponents" in titles
    assert "Laws of exponents" in titles
    assert "Contents" not in titles  # non-linear nav skipped
    # the 'Tiny' stub got merged into the previous section, not left on its own
    assert "Tiny" not in titles
    assert "Short." in book.sections[-1].text


def test_html_is_sanitised(tmp_path):
    book = parse_epub(_epub(tmp_path))
    html = "".join(s.html for s in book.sections)
    for bad in ("<script", "steal()", "onclick", "javascript:", "<style", "color:red", "tracker.example.com", "<a "):
        assert bad not in html, bad
    assert 'data-asset="OEBPS/images/graph.png"' in html  # relative path resolved
    assert 'alt="Graph of y = 2^x"' in html
    assert 'colspan="2"' in html
    assert "<em>[tracker]</em>" in html  # remote image dropped, alt text kept
    assert "<msup>" in html  # MathML kept for the browser to render
    assert "annotation" not in html


def test_split_inside_open_elements_is_well_formed(tmp_path):
    book = parse_epub(_epub(tmp_path))
    laws = next(s for s in book.sections if s.title == "Laws of exponents")
    # the section/div that were open at the split are re-opened and closed again
    assert laws.html.startswith("<section>") or laws.html.startswith("<h2>") or "<div>" in laws.html
    for tag in ("section", "div", "p", "table"):
        assert laws.html.count(f"<{tag}") == laws.html.count(f"</{tag}>"), tag


def test_text_uses_tex_annotation_and_figure_alt(tmp_path):
    book = parse_epub(_epub(tmp_path))
    laws = next(s for s in book.sections if s.title == "Laws of exponents")
    assert "$a^m \\times a^n = a^{m+n}$" in laws.text
    assert "[figure 1: Graph of y = 2^x]" in laws.text


def test_licence_detected_from_book(tmp_path):
    assert parse_epub(_epub(tmp_path)).licence == "CC BY 4.0"
    nd_front = FRONT.replace("Creative Commons Attribution 4.0 International License (CC BY 4.0)", "CC BY-ND 3.0")
    assert parse_epub(_epub(tmp_path, rights="", front=nd_front)).licence == "CC BY-ND 3.0"


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Creative Commons Attribution-NoDerivatives 4.0 International License (CC BY-ND 4.0)", "CC BY-ND 4.0"),
        ("Formoreinformationa bouttheCreativeComm onsAttribution-NoDerivs3.0", "CC BY-ND"),
        ("(CC BY-ND 3.0) license see http://creativecommons.org/licenses/by-nd/3.0/", "CC BY-ND 3.0"),
        ("licensed CC BY 3.0, see creativecommons.org/licenses/by/3.0/", "CC BY 3.0"),
        ("https://creativecommons.org/licenses/by/4.0/", "CC BY 4.0"),
        ("CC BY-NC-SA 4.0", "CC BY-NC-SA 4.0"),
        ("This book is released under the CC-BY 4.0 license.", "CC BY 4.0"),  # Siyavula ePub wording
        ("released under the CC-BY-ND 3.0 license", "CC BY-ND 3.0"),
        ("All rights reserved", None),
    ],
)
def test_detect_licence(text, expected):
    assert detect_licence(text) == expected


def test_licence_gate():
    assert licence_decision("CC BY 4.0", "CC BY", False)[0] == "CC BY 4.0"
    assert licence_decision("CC BY-SA 4.0", "CC BY", False)[0] == "CC BY-SA 4.0"
    assert licence_decision("CC BY-ND 3.0", "CC BY", False)[0] is None
    assert licence_decision("CC BY-NC 4.0", "CC BY", False)[0] is None
    assert licence_decision("CC BY-ND 3.0", "CC BY", True)[0] == "CC BY-ND 3.0"
    licence, msg = licence_decision(None, "CC BY", False)
    assert licence == "CC BY" and "WARNING" in msg
    assert licence_family("CC BY-ND 3.0") == "CC BY-ND"


def test_read_asset_only_serves_images(tmp_path):
    path = _epub(tmp_path)
    data, media = read_asset(path, "OEBPS/images/graph.png")
    assert media == "image/png" and data.startswith(b"\x89PNG")
    with pytest.raises(KeyError):
        read_asset(path, "OEBPS/evil.js")
    with pytest.raises(KeyError):
        read_asset(path, "OEBPS/missing.png")
    with pytest.raises(KeyError):
        read_asset(path, "../../etc/passwd.png")


SIYAVULA_LIKE = """<html><head><script src="mathjax/MathJax.js"></script></head><body>
<div class="worked_example evil"><h1 class="title">Worked example 1: Rational numbers</h1>
<div class="question"><p>Which of these is rational? <img class="math-inline" src="equation/a1.png"/> or
<img class="math-inline" src="equation/b2.png"/>. Think about whether each decimal terminates or repeats,
and use that to decide. Write down your reasons for each one before checking the answer below.</p></div>
<img class="math-block" src="equation/c3.png"/>
<div class="figure"><img src="tikzpicture/d4.png" alt="d4.png"/></div>
</div></body></html>"""


def test_siyavula_equation_images_are_numbered(tmp_path):
    from app.services.epub import Section, split_document

    sections = []
    split_document(SIYAVULA_LIKE, "OPS/x/ch.html", lambda p: True, sections)
    sec = [s for s in sections if s.text.strip()][0]
    assert sec.title == "Worked example 1: Rational numbers"
    assert 'class="eq-inline" data-eq="1"' in sec.html and 'data-eq="2"' in sec.html
    assert 'class="eq-block" data-eq="3"' in sec.html
    assert 'data-fig="1" alt=""' in sec.html  # hash filename alt dropped
    assert "[eq 1]" in sec.text and "[eq 3]" in sec.text and "[figure 1]" in sec.text
    assert 'class="sv-worked_example"' in sec.html and "evil" not in sec.html
    assert 'class="sv-question"' in sec.html
    assert "mathjax" not in sec.html.lower()


def test_nav_document_skipped_by_property(tmp_path):
    opf = OPF.replace('<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml"/>',
                      '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>')
    opf = opf.replace('<itemref idref="nav" linear="no"/>', '<itemref idref="nav"/>')
    path = tmp_path / "b.epub"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("META-INF/container.xml", CONTAINER)
        zf.writestr("OEBPS/content.opf", opf.format(rights="CC BY 4.0"))
        zf.writestr("OEBPS/front.xhtml", FRONT)
        zf.writestr("OEBPS/nav.xhtml", "<html><body><h1>Contents</h1><p>" + "x " * 400 + "</p></body></html>")
        zf.writestr("OEBPS/text/chapter 1.xhtml", CHAPTER)
        zf.writestr("OEBPS/images/graph.png", b"png")
    assert "Contents" not in [s.title for s in parse_epub(path).sections]


def test_merged_sections_keep_equation_numbers_unique():
    from app.services.epub import Section, merge_small_sections, split_document

    html = """<html><body><h2>Long section</h2><p>""" + "words " * 80 + """<img class="math-inline" src="e/1.png"/></p>
    <h2>Stub</h2><p>Note: <img class="math-inline" src="e/2.png"/></p></body></html>"""
    raw = []
    split_document(html, "OPS/c.html", lambda p: True, raw)
    merged = merge_small_sections(raw, min_chars=600)
    assert len(merged) == 1
    sec = merged[0]
    assert sec.equations == 2
    assert 'data-eq="1"' in sec.html and 'data-eq="2"' in sec.html
    assert sec.html.count('data-eq="1"') == 1
    assert "[eq 1]" in sec.text and "[eq 2]" in sec.text
