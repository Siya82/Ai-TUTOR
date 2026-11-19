/*
 * NEW 19 Nov 2026 (ADR-041). The textbook chapter for the topic the learner
 * picked, shown beside the tutor chat: e.g. Algebraic Expressions opens
 * "Chapter 1: Algebraic expressions" of Everything Maths Grade 10. Reading
 * stays inside that chapter; "Ask THUTOra" (about the section or a
 * highlighted part) drops straight into the chat next to it.
 */
import { useEffect, useState } from "react";
import { X } from "lucide-react";
import { fetchChaptersForTopic } from "../api";
import { BookReader } from "./LibraryView";

export default function TopicTextbook({ auth, onLogout, topicId, topicName, onAsk, onClose, onOpenInLibrary }) {
  const [chapters, setChapters] = useState(null);
  const [error, setError] = useState(null);
  const [page, setPage] = useState(null);

  useEffect(() => {
    if (!topicId) return undefined;
    let cancelled = false;
    const id = setTimeout(() => {
      setChapters(null);
      setPage(null);
      setError(null);
      fetchChaptersForTopic(auth.token, topicId)
        .then((list) => {
          if (cancelled) return;
          setChapters(list);
          if (list.length) setPage(list[0].start_page);
        })
        .catch((err) => !cancelled && setError(err.message));
    }, 0);
    return () => {
      cancelled = true;
      clearTimeout(id);
    };
  }, [auth.token, topicId]);

  const chapter = chapters?.[0];

  return (
    <section className="topic-book" aria-label="Textbook">
      <div className="topic-book__header">
        <div>
          <div className="topic-book__eyebrow">Textbook · {topicName}</div>
          <div className="topic-book__chapter">
            {chapter ? chapter.chapter || chapter.book_title : chapters ? "No chapter yet" : "Finding the chapter…"}
          </div>
          {chapter && <div className="reader__muted">{chapter.book_title}</div>}
        </div>
        <button type="button" className="topic-book__close" onClick={onClose} aria-label="Hide textbook">
          <X size={20} aria-hidden="true" />
        </button>
      </div>
      {error && <div className="chat-screen__error">{error}</div>}
      {chapters && chapters.length === 0 && (
        <p className="reader__muted topic-book__empty">
          There's no textbook chapter linked to this topic yet. Keep asking THUTOra in the chat, or browse the
          Library.
        </p>
      )}
      {chapter && page != null && (
        <BookReader
          key={`${chapter.book_id}-${topicId}`}
          auth={auth}
          onLogout={onLogout}
          bookId={chapter.book_id}
          page={page}
          onPageChange={setPage}
          range={{ start: chapter.start_page, end: chapter.end_page }}
          onClose={() => onOpenInLibrary(chapter.book_id, page)}
          closeLabel="Open in Library"
          onAsk={onAsk}
        />
      )}
    </section>
  );
}
