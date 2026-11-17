"""
ePub support for the e-book library (ADR-032, ePub addendum).

NEW 17 Nov 2026. Siyavula publishes its CC BY (unbranded) textbooks as
ePub; the PDFs are the branded CC BY-ND editions. So the Library reads
ePubs as well as PDFs.

An ePub is a zip of XHTML files plus images, ordered by the OPF "spine".
There are no printed pages, so a book is split into **sections** at
headings (h1-h3); a section plays the role a page plays for a PDF
(BookPage.page_number is the section number).

Standard library only (zipfile, xml.etree, html.parser), deliberately:
new pip installs are blocked on the dev laptop by Windows Application
Control, and nothing here needs more.

Everything that leaves this module as HTML is rebuilt from an allow-list
of tags and attributes. Scripts, styles, event handlers, links, iframes
and forms never get through. Images are rewritten to
`<img data-asset="<zip path>">`; the reader fetches them through an
authenticated endpoint (`/books/{id}/assets?path=...`).
"""

from __future__ import annotations

import posixpath
import re
import zipfile
from dataclasses import dataclass, field
from html import escape
from html.parser import HTMLParser
from typing import Optional
from urllib.parse import unquote
from xml.etree import ElementTree as ET

# --- licence detection --------------------------------------------------------

_LICENCE_PATTERNS = [
    # Most specific first. Text inside books is often broken by hyphenation or
    # missing spaces, so the patterns allow for that.
    (re.compile(r"CC\s*BY[\s-]*NC[\s-]*ND\s*(\d\.\d)?", re.I), "CC BY-NC-ND"),
    (re.compile(r"CC\s*BY[\s-]*NC[\s-]*SA\s*(\d\.\d)?", re.I), "CC BY-NC-SA"),
    (re.compile(r"CC\s*BY[\s-]*NC\s*(\d\.\d)?", re.I), "CC BY-NC"),
    (re.compile(r"CC\s*BY[\s-]*ND\s*(\d\.\d)?", re.I), "CC BY-ND"),
    (re.compile(r"CC\s*BY[\s-]*SA\s*(\d\.\d)?", re.I), "CC BY-SA"),
    (re.compile(r"Attribution[\s-]*No[\s-]*Deriv", re.I), "CC BY-ND"),
    (re.compile(r"Attribution[\s-]*Non[\s-]*Commercial", re.I), "CC BY-NC"),
    (re.compile(r"CC\s*BY\s*(\d\.\d)", re.I), "CC BY"),
    (re.compile(r"creativecommons\.org/licenses/by/(\d\.\d)", re.I), "CC BY"),
    (re.compile(r"Creative\s*Commons\s*Attribution\s*(\d\.\d)", re.I), "CC BY"),
]
_VERSION = re.compile(r"(?:licenses/[a-z-]+/|\b)(\d\.\d)\b")

# Licences that allow THUTOra's commercial use including AI explanations and
# search chunks (adaptation). See ADR-032.
COMMERCIAL_ADAPTABLE = {"CC BY", "CC BY-SA"}


def detect_licence(text: str) -> Optional[str]:
    """Best guess at the Creative Commons licence stated in a book's front
    matter, e.g. "CC BY 4.0" or "CC BY-ND 3.0". None if nothing found.
    Restrictive licences are matched before plain CC BY, so a book that
    mentions both (e.g. "the branded edition is CC BY-ND") is never
    under-reported as plain CC BY."""
    for pattern, name in _LICENCE_PATTERNS:
        m = pattern.search(text)
        if not m:
            continue
        version = m.group(1) if m.groups() and m.group(1) else None
        if version is None:
            near = _VERSION.search(text[m.start(): m.end() + 120])
            version = near.group(1) if near else None
        return f"{name} {version}" if version else name
    return None


def licence_family(licence: Optional[str]) -> Optional[str]:
    """'CC BY-ND 3.0' -> 'CC BY-ND'."""
    if not licence:
        return None
    return re.sub(r"\s*\d\.\d$", "", licence.strip())


# --- OPF / spine ---------------------------------------------------------------

_NS = {
    "c": "urn:oasis:names:tc:opendocument:xmlns:container",
    "opf": "http://www.idpf.org/2007/opf",
    "dc": "http://purl.org/dc/elements/1.1/",
}


@dataclass
class EpubDoc:
    title: Optional[str]
    rights: Optional[str]
    spine: list[str]  # zip paths of XHTML documents, in reading order


def read_package(zf: zipfile.ZipFile) -> EpubDoc:
    container = ET.fromstring(zf.read("META-INF/container.xml"))
    rootfile = container.find(".//c:rootfile", _NS)
    if rootfile is None:
        raise ValueError("Not a valid ePub: META-INF/container.xml has no rootfile")
    opf_path = rootfile.get("full-path")
    opf_dir = posixpath.dirname(opf_path)
    opf = ET.fromstring(zf.read(opf_path))

    def text_of(tag: str) -> Optional[str]:
        el = opf.find(f".//dc:{tag}", _NS)
        return el.text.strip() if el is not None and el.text else None

    manifest = {}
    for item in opf.findall(".//opf:manifest/opf:item", _NS):
        manifest[item.get("id")] = (
            posixpath.normpath(posixpath.join(opf_dir, unquote(item.get("href", "")))),
            item.get("media-type", ""),
        )
    spine = []
    for ref in opf.findall(".//opf:spine/opf:itemref", _NS):
        if ref.get("linear", "yes") == "no":
            continue
        path, media = manifest.get(ref.get("idref"), (None, None))
        if path and "html" in media:
            spine.append(path)
    return EpubDoc(title=text_of("title"), rights=text_of("rights"), spine=spine)


# --- sanitising + splitting -----------------------------------------------------

_ALLOWED = {
    # text structure
    "p", "div", "span", "section", "article", "h1", "h2", "h3", "h4", "h5", "h6",
    "ul", "ol", "li", "dl", "dt", "dd", "blockquote", "pre", "code", "br", "hr",
    "em", "strong", "b", "i", "u", "sub", "sup", "small",
    "table", "thead", "tbody", "tfoot", "tr", "td", "th", "caption",
    "figure", "figcaption", "img",
    # MathML (Chrome/Firefox/Safari render it natively)
    "math", "mrow", "mi", "mn", "mo", "ms", "mtext", "mspace", "msup", "msub",
    "msubsup", "mfrac", "msqrt", "mroot", "mover", "munder", "munderover",
    "mtable", "mtr", "mtd", "mstyle", "mpadded", "mphantom", "menclose",
    "mfenced", "semantics",
}
_DROP_WITH_CONTENT = {"script", "style", "head", "title", "iframe", "object", "embed",
                      "form", "button", "input", "select", "textarea", "svg", "annotation-xml",
                      "annotation", "noscript", "template", "nav"}
_VOID = {"br", "hr", "img", "mspace"}
_ALLOWED_ATTRS = {
    "td": {"colspan", "rowspan"},
    "th": {"colspan", "rowspan"},
    "ol": {"start"},
    "math": {"display"},
    "mo": {"stretchy", "fence", "separator"},
    "mi": {"mathvariant"},
    "mfrac": {"linethickness"},
    "mstyle": {"displaystyle", "scriptlevel"},
    "menclose": {"notation"},
    "mfenced": {"open", "close", "separators"},
}
_BLOCK_FOR_TEXT = {"p", "div", "section", "article", "li", "tr", "h1", "h2", "h3", "h4",
                   "h5", "h6", "br", "table", "figure", "figcaption", "blockquote", "pre", "dt", "dd", "hr"}
SPLIT_HEADINGS = {"h1", "h2", "h3"}
MIN_SECTION_CHARS = 300  # merge tinier sections forward, so the reader isn't full of stubs


@dataclass
class Section:
    title: str
    html_parts: list[str] = field(default_factory=list)
    text_parts: list[str] = field(default_factory=list)

    @property
    def html(self) -> str:
        return "".join(self.html_parts).strip()

    @property
    def text(self) -> str:
        t = "".join(self.text_parts)
        t = re.sub(r"[ \t\r\f\v]+", " ", t)
        t = re.sub(r" *\n *", "\n", t)
        return re.sub(r"\n{3,}", "\n\n", t).strip()


class _Splitter(HTMLParser):
    """Rebuilds allowed HTML, starting a new Section at each h1-h3. When a
    split happens inside open elements, those elements are closed in the
    old section and re-opened in the new one, so every section is
    well-formed on its own."""

    def __init__(self, doc_path: str, asset_exists, sections: list[Section]):
        super().__init__(convert_charrefs=True)
        self.doc_dir = posixpath.dirname(doc_path)
        self.asset_exists = asset_exists
        self.sections = sections
        self.open: list[tuple[str, str]] = []  # (tag, rendered open tag)
        self.drop_depth = 0
        self.heading: Optional[str] = None  # tag name while inside a split heading
        self.heading_text: list[str] = []
        self.math_depth = 0
        self.tex_parts: list[str] = []
        self.math_text_start = 0
        self.in_tex_annotation = False

    @property
    def cur(self) -> Section:
        return self.sections[-1]

    def _attrs(self, tag, attrs) -> str:
        out = []
        allowed = _ALLOWED_ATTRS.get(tag, set())
        for k, v in attrs:
            k = k.lower()
            if tag == "img":
                continue
            if k in allowed and v is not None and not v.lower().startswith("javascript"):
                out.append(f' {k}="{escape(v, quote=True)}"')
        if tag == "img":
            a = dict((k.lower(), v) for k, v in attrs)
            src = a.get("src") or ""
            path = posixpath.normpath(posixpath.join(self.doc_dir, unquote(src.split("#")[0])))
            if src and not src.startswith(("http:", "https:", "data:")) and self.asset_exists(path):
                out.append(f' data-asset="{escape(path, quote=True)}"')
            out.append(f' alt="{escape(a.get("alt") or "", quote=True)}"')
        return "".join(out)

    def _local_image(self, attrs) -> bool:
        src = dict((k.lower(), v) for k, v in attrs).get("src") or ""
        if not src or src.startswith(("http:", "https:", "data:", "//")):
            return False
        path = posixpath.normpath(posixpath.join(self.doc_dir, unquote(src.split("#")[0])))
        return self.asset_exists(path)

    def _new_section(self, title: str) -> None:
        for tag, _ in reversed(self.open):
            self.cur.html_parts.append(f"</{tag}>")
        self.sections.append(Section(title=title))
        for _, rendered in self.open:
            self.cur.html_parts.append(rendered)

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if self.drop_depth or tag in _DROP_WITH_CONTENT:
            if tag == "annotation" and self.math_depth and any(
                k == "encoding" and v and "tex" in v.lower() for k, v in attrs
            ):
                self.in_tex_annotation = True
                return
            if tag not in _VOID:
                self.drop_depth += 1
            return
        if self.heading is not None:
            return  # markup inside a split heading: only its text is kept
        if tag in SPLIT_HEADINGS:
            self.heading = tag
            self.heading_text = []
            return
        if tag == "math":
            self.math_depth += 1
            if self.math_depth == 1:
                self.tex_parts = []
                self.math_text_start = len(self.cur.text_parts)
        if tag not in _ALLOWED:
            return  # unknown wrapper: keep its children, drop the tag
        if tag == "img" and not self._local_image(attrs):
            # Remote or missing images are never fetched (no tracking pixels,
            # no broken icons): keep the alt text instead.
            alt = dict(attrs).get("alt")
            if alt:
                self.cur.html_parts.append(f"<em>[{escape(alt)}]</em>")
                self.cur.text_parts.append(f"[Figure: {alt}]")
            return
        rendered = f"<{tag}{self._attrs(tag, attrs)}>"
        self.cur.html_parts.append(rendered)
        if tag in _BLOCK_FOR_TEXT:
            self.cur.text_parts.append("\n")
        if tag == "img":
            alt = dict(attrs).get("alt")
            if alt:
                self.cur.text_parts.append(f"[Figure: {alt}]")
        if tag not in _VOID:
            self.open.append((tag, rendered))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag.lower() not in _VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if self.in_tex_annotation and tag == "annotation":
            self.in_tex_annotation = False
            return
        if self.drop_depth:
            if tag in _DROP_WITH_CONTENT or tag not in _VOID:
                self.drop_depth -= 1
            return
        if self.heading is not None:
            if tag != self.heading:
                return
            title = re.sub(r"\s+", " ", "".join(self.heading_text)).strip()
            self.heading = None
            if self.cur.html or self.cur.text:
                self._new_section(title)
            else:
                self.cur.title = title
            self.cur.html_parts.append(f"<{tag}>{escape(title)}</{tag}>")
            self.cur.text_parts.append(f"\n{title}\n")
            return
        if tag == "math" and self.math_depth:
            self.math_depth -= 1
            if self.math_depth == 0 and self.tex_parts:
                # Prefer the TeX annotation for the text the tutor sees.
                del self.cur.text_parts[self.math_text_start:]
                self.cur.text_parts.append(f" ${''.join(self.tex_parts).strip()}$ ")
        if tag not in _ALLOWED or tag in _VOID:
            return
        for i in range(len(self.open) - 1, -1, -1):
            if self.open[i][0] == tag:
                for t, _ in reversed(self.open[i:]):
                    self.cur.html_parts.append(f"</{t}>")
                del self.open[i:]
                break
        if tag in _BLOCK_FOR_TEXT:
            self.cur.text_parts.append("\n")

    def handle_data(self, data):
        if self.in_tex_annotation:
            self.tex_parts.append(data)
            return
        if self.drop_depth:
            return
        if self.heading is not None:
            self.heading_text.append(data)
            return
        self.cur.html_parts.append(escape(data, quote=False))
        self.cur.text_parts.append(data)

    def close(self):
        super().close()
        for tag, _ in reversed(self.open):
            self.cur.html_parts.append(f"</{tag}>")
        self.open = []


def split_document(xhtml: str, doc_path: str, asset_exists, sections: list[Section]) -> None:
    """Appends this XHTML document's content to `sections` (starting a new
    section at the document start and at every h1-h3)."""
    sections.append(Section(title=""))
    parser = _Splitter(doc_path, asset_exists, sections)
    parser.feed(xhtml)
    parser.close()


def merge_small_sections(sections: list[Section], min_chars: int = MIN_SECTION_CHARS) -> list[Section]:
    """Tidies the raw split:
    - sections with no text at all (only wrapper tags) are dropped;
    - a heading-only stub (e.g. a chapter title page) is carried FORWARD
      into the next section, so the chapter title stays with its content;
    - any other short section (a two-line note after a heading) is folded
      BACK into the previous section, which it belongs to.
    """
    out: list[Section] = []
    carry: Optional[Section] = None
    for s in sections:
        if not s.text.strip():
            continue
        if carry is not None:
            s = Section(
                title=s.title or carry.title,
                html_parts=[carry.html, s.html],
                text_parts=[carry.text, "\n\n", s.text],
            )
            carry = None
        body_chars = len(s.text) - len(s.title)
        if len(s.text) < min_chars:
            if body_chars < 40 or not out:
                carry = s  # heading-only stub (or nothing before it): attach forward
                continue
            prev = out[-1]
            out[-1] = Section(title=prev.title, html_parts=[prev.html, s.html], text_parts=[prev.text, "\n\n", s.text])
            continue
        out.append(s)
    if carry is not None:
        if out:
            last = out[-1]
            out[-1] = Section(title=last.title, html_parts=[last.html, carry.html], text_parts=[last.text, "\n\n", carry.text])
        else:
            out.append(carry)
    for i, s in enumerate(out, start=1):
        if not s.title:
            s.title = f"Section {i}"
    return out


@dataclass
class ParsedEpub:
    title: Optional[str]
    rights: Optional[str]
    licence: Optional[str]
    sections: list[Section]


def parse_epub(path) -> ParsedEpub:
    with zipfile.ZipFile(path) as zf:
        pkg = read_package(zf)
        names = set(zf.namelist())
        sections: list[Section] = []
        front_text = []
        for doc in pkg.spine:
            if doc not in names:
                continue
            xhtml = zf.read(doc).decode("utf-8", errors="replace")
            split_document(xhtml, doc, lambda p: p in names, sections)
        merged = merge_small_sections(sections)
        for s in merged[:6]:
            front_text.append(s.text)
    licence = detect_licence((pkg.rights or "") + "\n" + "\n".join(front_text))
    return ParsedEpub(title=pkg.title, rights=pkg.rights, licence=licence, sections=merged)


_ASSET_TYPES = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif",
    ".svg": "image/svg+xml", ".webp": "image/webp",
}


def read_asset(path, member: str) -> tuple[bytes, str]:
    """An image from inside the ePub. Only image types are served; anything
    else (scripts, HTML) raises KeyError, as does a missing member."""
    ext = posixpath.splitext(member)[1].lower()
    media = _ASSET_TYPES.get(ext)
    if media is None:
        raise KeyError(member)
    with zipfile.ZipFile(path) as zf:
        return zf.read(member), media
