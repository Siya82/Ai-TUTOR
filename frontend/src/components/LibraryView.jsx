/*
 * NEW 17 Nov 2026 (ADR-032, e-book library and reader). The learner's
 * "Library" view in ChatScreen.jsx:
 *
 *   - a list of openly-licensed books (Siyavula CC-BY) at or below their grade;
 *   - a reader that downloads ONE page at a time (a small single-page PDF,
 *     rendered with pdf.js) so mobile data isn't spent on whole books, plus a
 *     "Text" view that uses even less data and lets the learner select text;
 *   - "Ask THUTOra about this page" / "Ask about what I highlighted", which
 *     hand the page reference back to ChatScreen via onAsk().
 *
 * The CC-BY attribution is shown under every page, as the licence requires.
 *
 * UPDATED 17 Nov 2026 (ADR-032 ePub addendum): Siyavula's CC BY editions are
 * ePubs, which have no printed pages. An ePub book is read SECTION by section
 * (split at headings on import); its HTML was sanitised server-side, and its
 * images are fetched with the learner's token and shown as blob URLs.
 */

import { useEffect, useRef, useState } from "react";
import * as pdfjsLib from "pdfjs-dist";
import pdfWorkerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import { fetchBook, fetchBookAsset, fetchBookPage, fetchBookPagePdf, fetchBooks } from "../api";

pdfjsLib.GlobalWorkerOptions.workerSrc = pdfWorkerUrl;

export default function LibraryView({ auth, onLogout, position, onPositionChange, onAsk }) {
  // position: { bookId, page } | null -- owned by ChatScreen so the reader
  // reopens on the same page after the learner asks a question.
  if (position?.bookId) {
    return (
      <BookReader
        key={position.bookId}
        auth={auth}
        onLogout={onLogout}
        bookId={position.bookId}
        page={position.page || 1}
        onPageChange={(page) => onPositionChange({ bookId: position.bookId, page })}
        onClose={() => onPositionChange(null)}
        onAsk={onAsk}
      />
    );
  }
  return (
    <BookList auth={auth} onLogout={onLogout} onOpen={(bookId) => onPositionChange({ bookId, page: 1 })} />
  );
}

function BookList({ auth, onLogout, onOpen }) {
  const [books, setBooks] = useState(null);
  const [error, setError] = useState(null);
  const onLogoutRef = useRef(onLogout);

  useEffect(() => {
    let cancelled = false;
    fetchBooks(auth.token)
      .then((b) => {
        if (!cancelled) setBooks(b);
      })
      .catch((err) => {
        if (cancelled) return;
        if (err.status === 401) {
          onLogoutRef.current();
          return;
        }
        setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, [auth.token]);

  if (error) return <div className="chat-screen__error">{error}</div>;
  if (!books) return <div className="library__muted">Loading your library…</div>;
  if (books.length === 0) {
    return (
      <div className="library">
        <h2 className="library__heading">Library</h2>
        <p className="library__muted">
          No books have been added yet. Once your school's THUTOra administrator loads the textbooks,
          they'll appear here.
        </p>
      </div>
    );
  }

  const grades = [...new Set(books.map((b) => b.grade))].sort((a, b) => a - b);
  return (
    <div className="library">
      <h2 className="library__heading">Library</h2>
      <p className="library__muted">
        Read your textbooks here. Stuck on something? Ask THUTOra about the page, or highlight the bit
        you don't understand.
      </p>
      {grades.map((g) => (
        <section key={g} className="library__grade">
          <h3 className="library__grade-heading">Grade {g}</h3>
          <div className="library__books">
            {books
              .filter((b) => b.grade === g)
              .map((b) => (
                <button
                  key={b.id}
                  type="button"
                  className="book-card"
                  onClick={() => onOpen(b.id)}
                  disabled={b.page_count === 0}
                >
                  <span className="book-card__subject">{b.subject_name}</span>
                  <span className="book-card__title">{b.title}</span>
                  <span className="book-card__meta">
                    {b.page_count} {b.format === "epub" ? "sections" : "pages"} · {b.publisher || "Open textbook"} ·{" "}
                    {b.licence}
                  </span>
                </button>
              ))}
          </div>
        </section>
      ))}
    </div>
  );
}

function BookReader({ auth, onLogout, bookId, page, onPageChange, onClose, onAsk }) {
  const [book, setBook] = useState(null);
  const [pageData, setPageData] = useState(null);
  const [mode, setMode] = useState("page"); // "page" | "text"
  const [error, setError] = useState(null);
  const [selection, setSelection] = useState("");
  const [pageInput, setPageInput] = useState(String(page));
  const onLogoutRef = useRef(onLogout);

  const handleErr = (err) => {
    if (err.status === 401) {
      onLogoutRef.current();
      return;
    }
    setError(err.message);
  };

  useEffect(() => {
    let cancelled = false;
    fetchBook(auth.token, bookId)
      .then((b) => {
        if (cancelled) return;
        setBook(b);
        if (!b.file_available || b.format === "epub") setMode("text");
      })
      .catch((err) => !cancelled && handleErr(err));
    return () => {
      cancelled = true;
    };
  }, [auth.token, bookId]);

  useEffect(() => {
    let cancelled = false;
    fetchBookPage(auth.token, bookId, page)
      .then((p) => {
        if (cancelled) return;
        setPageData(p);
        setError(null);
        setSelection("");
        setPageInput(String(page));
      })
      .catch((err) => !cancelled && handleErr(err));
    return () => {
      cancelled = true;
    };
  }, [auth.token, bookId, page]);

  const pageCount = book?.page_count || pageData?.page_count || 0;
  const isEpub = book?.format === "epub";
  const goTo = (n) => {
    const target = Math.min(Math.max(1, n), pageCount || 1);
    if (target !== page) onPageChange(target);
  };

  const captureSelection = () => {
    const text = window.getSelection()?.toString().trim() || "";
    setSelection(text.slice(0, 1500));
  };

  const ask = (selectedText) =>
    onAsk({
      bookId,
      bookTitle: book?.title || "",
      subjectId: book?.subject_id,
      pageNumber: page,
      sectionTitle: isEpub ? pageData?.title || "" : "",
      topicId: pageData?.topic_id || null,
      selectedText: selectedText || "",
    });

  return (
    <div className="reader">
      <div className="reader__toolbar">
        <button type="button" className="reader__link" onClick={onClose}>
          ← Library
        </button>
        <div className="reader__title">{book?.title || "…"}</div>
        <div className="reader__nav">
          <button type="button" onClick={() => goTo(page - 1)} disabled={page <= 1} aria-label="Previous page">
            ‹
          </button>
          {isEpub ? (
            <select
              className="reader__section-select"
              value={page}
              onChange={(e) => goTo(Number(e.target.value))}
              aria-label="Section"
            >
              {(book.sections || []).map((sec) => (
                <option key={sec.number} value={sec.number}>
                  {sec.number}. {sec.title}
                </option>
              ))}
            </select>
          ) : (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              goTo(Number(pageInput) || page);
            }}
          >
            <input
              className="reader__page-input"
              value={pageInput}
              onChange={(e) => setPageInput(e.target.value.replace(/\D/g, ""))}
              aria-label="Page number"
            />
          </form>
          )}
          <span className="reader__muted">/ {pageCount || "…"}</span>
          <button
            type="button"
            onClick={() => goTo(page + 1)}
            disabled={pageCount > 0 && page >= pageCount}
            aria-label="Next page"
          >
            ›
          </button>
        </div>
        {!isEpub && (
        <div className="reader__mode" role="group" aria-label="Reading mode">
          <button
            type="button"
            className={mode === "page" ? "reader__mode--active" : ""}
            onClick={() => setMode("page")}
            disabled={book && !book.file_available}
            title="The page as printed"
          >
            Page
          </button>
          <button
            type="button"
            className={mode === "text" ? "reader__mode--active" : ""}
            onClick={() => setMode("text")}
            title="Text only — uses less data, and you can highlight"
          >
            Text
          </button>
        </div>
        )}
      </div>

      {error && <div className="chat-screen__error">{error}</div>}

      <div className="reader__body">
        {!book ? (
          <p className="reader__muted">Loading book…</p>
        ) : isEpub ? (
          pageData ? (
            <EpubSection
              token={auth.token}
              bookId={bookId}
              html={pageData.html || ""}
              onSelect={captureSelection}
            />
          ) : (
            <p className="reader__muted">Loading section…</p>
          )
        ) : mode === "page" ? (
          <PdfPage token={auth.token} bookId={bookId} page={page} onError={handleErr} />
        ) : pageData ? (
          pageData.has_text ? (
            <div className="reader__text" onMouseUp={captureSelection} onTouchEnd={captureSelection} onKeyUp={captureSelection}>
              {pageData.text}
            </div>
          ) : (
            <p className="reader__muted">
              This page has no text to show (it may be a picture or diagram). Switch to Page view, or
              ask THUTOra about the page.
            </p>
          )
        ) : (
          <p className="reader__muted">Loading page…</p>
        )}
      </div>

      <div className="reader__ask">
        <button type="button" className="reader__ask-button" onClick={() => ask("")} disabled={!pageData}>
          {isEpub ? "Ask THUTOra about this section" : "Ask THUTOra about this page"}
        </button>
        {mode === "text" || isEpub ? (
          <button
            type="button"
            className="reader__ask-button reader__ask-button--secondary"
            onClick={() => ask(selection)}
            disabled={!selection}
            title={selection ? `“${selection.slice(0, 80)}”` : "Highlight some text first"}
          >
            {selection ? "Ask about what I highlighted" : "Highlight text to ask about it"}
          </button>
        ) : (
          pageData?.has_text && (
            <span className="reader__muted">Switch to Text to highlight a specific part.</span>
          )
        )}
      </div>

      <div className="reader__footer">
        {pageData?.topic_name && <span>Topic: {pageData.topic_name} · </span>}
        <span>{book?.attribution}</span>
      </div>
    </div>
  );
}

function PdfPage({ token, bookId, page, onError }) {
  const canvasRef = useRef(null);
  const wrapRef = useRef(null);
  const [loading, setLoading] = useState(true);
  const onErrorRef = useRef(onError);

  useEffect(() => {
    let cancelled = false;
    let renderTask = null;
    let doc = null;
    (async () => {
      try {
        const data = await fetchBookPagePdf(token, bookId, page);
        if (cancelled) return;
        doc = await pdfjsLib.getDocument({ data }).promise;
        const pdfPage = await doc.getPage(1); // the server sends just this one page
        if (cancelled) return;
        const canvas = canvasRef.current;
        const width = wrapRef.current?.clientWidth || 700;
        const base = pdfPage.getViewport({ scale: 1 });
        const ratio = window.devicePixelRatio || 1;
        const viewport = pdfPage.getViewport({ scale: (width / base.width) * ratio });
        canvas.width = viewport.width;
        canvas.height = viewport.height;
        canvas.style.width = `${viewport.width / ratio}px`;
        canvas.style.height = `${viewport.height / ratio}px`;
        renderTask = pdfPage.render({ canvasContext: canvas.getContext("2d"), viewport });
        await renderTask.promise;
        if (!cancelled) setLoading(false);
      } catch (err) {
        if (!cancelled && err?.name !== "RenderingCancelledException") onErrorRef.current(err);
      }
    })();
    return () => {
      cancelled = true;
      renderTask?.cancel();
      doc?.destroy();
      setLoading(true);
    };
  }, [token, bookId, page]);

  return (
    <div className="reader__page" ref={wrapRef}>
      {loading && <p className="reader__muted">Loading page…</p>}
      <canvas ref={canvasRef} className="reader__canvas" aria-label={`Page ${page}`} />
    </div>
  );
}

// NEW (ADR-032 ePub addendum). One ePub section. The HTML was rebuilt from an
// allow-list at import time (no scripts, styles, links or event handlers), so
// it is safe to insert. Images carry data-asset paths and are loaded through
// the authenticated assets endpoint, then shown as blob URLs.
function EpubSection({ token, bookId, html, onSelect }) {
  const ref = useRef(null);

  useEffect(() => {
    const root = ref.current;
    if (!root) return undefined;
    let cancelled = false;
    const urls = [];
    root.querySelectorAll("img[data-asset]").forEach((img) => {
      fetchBookAsset(token, bookId, img.getAttribute("data-asset"))
        .then((blob) => {
          if (cancelled) return;
          const url = URL.createObjectURL(blob);
          urls.push(url);
          img.src = url;
        })
        .catch(() => {
          img.replaceWith(document.createTextNode(img.alt ? `[Figure: ${img.alt}]` : "[Figure]"));
        });
    });
    root.scrollIntoView({ block: "start" });
    return () => {
      cancelled = true;
      urls.forEach((u) => URL.revokeObjectURL(u));
    };
  }, [token, bookId, html]);

  return (
    <div
      ref={ref}
      className="reader__epub"
      onMouseUp={onSelect}
      onTouchEnd={onSelect}
      onKeyUp={onSelect}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
