/*
 * ADR-051: the support queue. Replaces `python -m scripts.support`.
 * Replies appear in the school's Help Centre under "My tickets".
 */
import { useState } from "react";
import { CheckCircle2, RefreshCw, Send } from "lucide-react";
import { call } from "./api";
import { Banner, Chips } from "./shared";
import { useLoad } from "./useLoad";
import { STATUS_LABEL, ago, when } from "./format";

const VIEWS = [
  ["open", "Waiting for Zynora"],
  ["waiting_on_school", "Waiting on school"],
  ["resolved", "Resolved"],
];
const PRIORITIES = [
  ["p1", "Urgent"],
  ["p2", "A class is blocked"],
  ["p3", "Normal"],
  ["p4", "Suggestion"],
];

function TicketDetail({ token, number, onChanged }) {
  const { data: t, error, setData } = useLoad(`/tickets/${number}`, token);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  const act = async (path, body) => {
    setBusy(true);
    setErr(null);
    try {
      setData(await call(path, { token, method: "POST", body }));
      onChanged();
      return true;
    } catch (e) {
      setErr(e.message);
      return false;
    } finally {
      setBusy(false);
    }
  };
  const reply = async (resolve) => {
    if (!text.trim()) return;
    if (await act(`/tickets/${number}/reply`, { body: text, resolve })) setText("");
  };

  if (error) return <Banner>{error}</Banner>;
  if (!t) return <p className="muted">Loading…</p>;
  return (
    <section className="detail" aria-label={`Ticket ${t.number}`}>
      <header className="detail__head">
        <h2>
          #{t.number} {t.subject}
        </h2>
        <p className="muted">
          {t.school} · {t.from.name} ({t.from.login}) · {t.product.toUpperCase()} · {t.category}
        </p>
        <div className="row">
          <span className={`pill pill--${t.priority}`}>{t.priority_label}</span>
          <span className={`pill pill--status-${t.status}`}>{STATUS_LABEL[t.status]}</span>
          <label className="inline">
            Priority
            <select
              value={t.priority}
              disabled={busy}
              onChange={(e) => act(`/tickets/${number}/update`, { priority: e.target.value })}
            >
              {PRIORITIES.map(([id, label]) => (
                <option key={id} value={id}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          {t.status === "resolved" && (
            <button type="button" className="btn btn--ghost" disabled={busy} onClick={() => act(`/tickets/${number}/update`, { status: "open" })}>
              <RefreshCw size={16} aria-hidden="true" /> Reopen
            </button>
          )}
        </div>
        {t.context?.screen && <p className="muted">Screen: {t.context.screen}</p>}
      </header>
      <ol className="thread">
        {t.messages.map((m, i) => (
          <li key={i} className={`msg${m.from_zynora ? " msg--zynora" : ""}`}>
            <div className="msg__meta">
              {m.from_zynora ? `${m.author} (THUTOra support)` : m.author} · {when(m.at)}
            </div>
            <div className="msg__body">{m.body}</div>
          </li>
        ))}
      </ol>
      <Banner>{err}</Banner>
      <div className="reply">
        <label htmlFor="reply-text">Reply to the school</label>
        <textarea
          id="reply-text"
          rows={4}
          maxLength={5000}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Plain words, step by step. Never ask for a password."
        />
        <div className="row">
          <button type="button" className="btn btn--primary" disabled={busy || !text.trim()} onClick={() => reply(false)}>
            <Send size={16} aria-hidden="true" /> Reply
          </button>
          <button type="button" className="btn" disabled={busy || !text.trim()} onClick={() => reply(true)}>
            <CheckCircle2 size={16} aria-hidden="true" /> Reply and resolve
          </button>
        </div>
      </div>
    </section>
  );
}

export default function Tickets({ token }) {
  const [view, setView] = useState("open");
  const [selected, setSelected] = useState(null);
  const { data, error, reload } = useLoad(`/tickets?view=${view}`, token);
  const counts = data?.counts || {};

  return (
    <div className="split">
      <section className="list" aria-label="Tickets">
        <Chips
          label="Ticket status"
          value={view}
          onChange={(v) => {
            setView(v);
            setSelected(null);
          }}
          options={VIEWS.map(([id, label]) => [id, `${label}${counts[id] ? ` (${counts[id]})` : ""}`])}
        />
        <Banner>{error}</Banner>
        {data && data.tickets.length === 0 && <p className="muted">Nothing here.</p>}
        <ul className="items">
          {data?.tickets.map((t) => (
            <li key={t.number}>
              <button
                type="button"
                className={`item${selected === t.number ? " item--active" : ""}`}
                aria-current={selected === t.number ? "true" : undefined}
                onClick={() => setSelected(t.number)}
              >
                <span className="item__top">
                  <span className={`pill pill--${t.priority}`}>{t.priority_label}</span>
                  <span className="muted">#{t.number} · {ago(t.created_at)}</span>
                </span>
                <span className="item__title">{t.subject}</span>
                <span className="muted">{t.school}</span>
              </button>
            </li>
          ))}
        </ul>
      </section>
      {selected ? (
        <TicketDetail key={selected} token={token} number={selected} onChanged={reload} />
      ) : (
        <section className="detail detail--empty">
          <p className="muted">Choose a ticket. Urgent ones are at the top.</p>
        </section>
      )}
    </div>
  );
}
