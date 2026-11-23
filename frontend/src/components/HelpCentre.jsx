/*
 * NEW 23 Nov 2026 (ADR-050). The Help button and Help Centre.
 *
 *   product="teach" | "admin" | "insights"  staff: guides, contact support,
 *                                           and their tickets (school
 *                                           managers see the school's)
 *   product="learn"                         learners: ask your teacher;
 *                                           safeguarding numbers
 *   product="connect"                       parents: ask the school
 *
 * Learners and parents can't log tickets: the school is their first line
 * of support (POPIA: the school is the responsible party).
 */
import { useEffect, useRef, useState } from "react";
import { LifeBuoy, X } from "lucide-react";
import {
  createSupportTicket,
  fetchSupportContact,
  fetchSupportTicket,
  fetchSupportTickets,
  replySupportTicket,
  resolveSupportTicket,
} from "../api";
import { guidesFor } from "../help/guides";

const STAFF = new Set(["teach", "admin", "insights"]);
const STATUS_LABEL = { open: "With THUTOra support", waiting_on_school: "Waiting for you", resolved: "Resolved" };
const APP_VERSION = import.meta.env.VITE_APP_VERSION || "dev";

function ContactCard({ contact, intro }) {
  if (!contact) return null;
  return (
    <div className="help-contact">
      {intro && <p>{intro}</p>}
      <ul>
        <li>
          Email: <a href={`mailto:${contact.email}`}>{contact.email}</a>
        </li>
        {contact.whatsapp && (
          <li>
            WhatsApp:{" "}
            <a href={contact.whatsapp_link} target="_blank" rel="noreferrer">
              {contact.whatsapp}
            </a>
          </li>
        )}
        <li>Hours: {contact.hours}</li>
      </ul>
    </div>
  );
}

function Guides({ product }) {
  const [q, setQ] = useState("");
  const [openId, setOpenId] = useState(null);
  const all = guidesFor(product);
  const shown = q.trim()
    ? all.filter((g) => (g.title + " " + g.steps.join(" ")).toLowerCase().includes(q.trim().toLowerCase()))
    : all;
  return (
    <div>
      <input
        className="help-search"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Search the guides"
        aria-label="Search the guides"
      />
      {shown.length === 0 && <p className="admin-screen__muted">No guide matches. Try Contact support.</p>}
      <ul className="help-guides">
        {shown.map((g) => (
          <li key={g.id}>
            <button
              type="button"
              className="help-guides__title"
              aria-expanded={openId === g.id}
              onClick={() => setOpenId(openId === g.id ? null : g.id)}
            >
              {g.title}
            </button>
            {openId === g.id && (
              <ol className="help-guides__steps">
                {g.steps.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ol>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

function NewTicket({ token, product, contact, onCreated }) {
  const [form, setForm] = useState({ category: "", subject: "", body: "", blocking: false });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });
  const category = contact?.categories.find((c) => c.id === form.category);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const t = await createSupportTicket(token, {
        ...form,
        product,
        screen: window.location.pathname.slice(0, 80),
        app_version: APP_VERSION,
      });
      setForm({ category: "", subject: "", body: "", blocking: false });
      onCreated(t);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="help-form" onSubmit={submit}>
      <label>
        <span>What's it about?</span>
        <select value={form.category} onChange={set("category")} required>
          <option value="">Choose…</option>
          {contact?.categories.map((c) => (
            <option key={c.id} value={c.id}>
              {c.label}
            </option>
          ))}
        </select>
      </label>
      {category?.id === "safeguarding" && (
        <p className="help-urgent">
          If a learner is in danger right now, call the police on <strong>10111</strong> and follow your school's
          safeguarding process first. Childline: <strong>116</strong>. Then tell us here, with no more learner detail
          than we need.
        </p>
      )}
      {category?.urgent && category.id !== "safeguarding" && (
        <p className="help-urgent">
          Urgent tickets reach us straight away. During support hours you can also WhatsApp {contact.whatsapp}.
        </p>
      )}
      <label>
        <span>Short summary</span>
        <input value={form.subject} onChange={set("subject")} minLength={3} maxLength={150} required />
      </label>
      <label>
        <span>What happened? What did you expect?</span>
        <textarea value={form.body} onChange={set("body")} minLength={5} maxLength={4000} rows={5} required />
      </label>
      <p className="admin-screen__muted">
        Please don't include learners' full names, ID numbers or contact details. A login number is enough.
      </p>
      {category && !category.urgent && (
        <label className="help-check">
          <input type="checkbox" checked={form.blocking} onChange={set("blocking")} />
          <span>A class can't work because of this right now</span>
        </label>
      )}
      {error && <div className="admin-screen__error">{error}</div>}
      <button type="submit" className="answer-review__btn" disabled={busy}>
        {busy ? "Sending…" : "Send to THUTOra support"}
      </button>
    </form>
  );
}

function TicketThread({ token, id, onChanged }) {
  const [t, setT] = useState(null);
  const [reply, setReply] = useState("");
  const [error, setError] = useState("");
  const load = () => fetchSupportTicket(token, id).then(setT).catch((e) => setError(e.message));
  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);
  if (error) return <div className="admin-screen__error">{error}</div>;
  if (!t) return <p className="admin-screen__muted">Loading…</p>;

  async function send(e) {
    e.preventDefault();
    await replySupportTicket(token, id, reply.trim());
    setReply("");
    await load();
    onChanged();
  }
  async function resolve() {
    await resolveSupportTicket(token, id);
    await load();
    onChanged();
  }

  return (
    <div className="help-thread">
      <p className="help-thread__meta">
        Ticket {t.number} · {t.category_label} · {t.priority_label} · <strong>{STATUS_LABEL[t.status]}</strong>
      </p>
      <h3>{t.subject}</h3>
      <ol className="help-thread__messages">
        {t.messages.map((m, i) => (
          <li key={i} className={m.from_zynora ? "help-msg help-msg--zynora" : "help-msg"}>
            <span className="help-msg__who">
              {m.author} · {new Date(m.created_at).toLocaleString()}
            </span>
            <p>{m.body}</p>
          </li>
        ))}
      </ol>
      <form className="help-form" onSubmit={send}>
        <label>
          <span>{t.status === "resolved" ? "Not sorted after all? Reply to reopen" : "Reply"}</span>
          <textarea value={reply} onChange={(e) => setReply(e.target.value)} rows={3} maxLength={4000} required />
        </label>
        <div className="help-form__row">
          <button type="submit" className="answer-review__btn" disabled={!reply.trim()}>
            Send reply
          </button>
          {t.status !== "resolved" && (
            <button type="button" className="admin-screen__link-button" onClick={resolve}>
              Mark as resolved
            </button>
          )}
        </div>
      </form>
    </div>
  );
}

function Tickets({ token, refreshKey }) {
  const [rows, setRows] = useState(null);
  const [openId, setOpenId] = useState(null);
  const [tick, setTick] = useState(0);
  useEffect(() => {
    fetchSupportTickets(token).then(setRows).catch(() => setRows([]));
  }, [token, refreshKey, tick]);
  if (openId)
    return (
      <div>
        <button type="button" className="admin-screen__link-button" onClick={() => setOpenId(null)}>
          ← All tickets
        </button>
        <TicketThread token={token} id={openId} onChanged={() => setTick((n) => n + 1)} />
      </div>
    );
  if (!rows) return <p className="admin-screen__muted">Loading…</p>;
  if (rows.length === 0) return <p className="admin-screen__muted">No tickets yet.</p>;
  return (
    <ul className="help-tickets">
      {rows.map((t) => (
        <li key={t.id}>
          <button type="button" onClick={() => setOpenId(t.id)}>
            <span className={`help-status help-status--${t.status}`}>{STATUS_LABEL[t.status]}</span>
            <strong>
              {t.number}. {t.subject}
            </strong>
            <span className="admin-screen__muted">
              {t.priority_label} · updated {new Date(t.updated_at).toLocaleDateString()}
              {!t.mine && " · colleague's ticket"}
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}

function StaffHelp({ token, product, contact }) {
  const [tab, setTab] = useState("guides");
  const [created, setCreated] = useState(null);
  return (
    <>
      <div className="progress-filter" role="group" aria-label="Help sections">
        {[
          ["guides", "Guides"],
          ["contact", "Contact support"],
          ["tickets", "My tickets"],
        ].map(([id, label]) => (
          <button
            key={id}
            type="button"
            aria-pressed={tab === id}
            className={`progress-filter__chip${tab === id ? " progress-filter__chip--active" : ""}`}
            onClick={() => setTab(id)}
          >
            {label}
          </button>
        ))}
      </div>
      {tab === "guides" && <Guides product={product} />}
      {tab === "contact" && (
        <>
          {created && (
            <p className="help-done">
              Ticket {created.number} sent. We'll reply here under My tickets ({contact?.hours}).
            </p>
          )}
          <NewTicket
            token={token}
            product={product}
            contact={contact}
            onCreated={(t) => {
              setCreated(t);
            }}
          />
          <ContactCard contact={contact} intro="Can't use the form? Contact us directly:" />
        </>
      )}
      {tab === "tickets" && <Tickets token={token} refreshKey={created?.id} />}
    </>
  );
}

function LearnerHelp({ contact }) {
  return (
    <div className="help-simple">
      <p>
        <strong>Can't log in, or something isn't working?</strong> Ask your teacher. They can reset your password and
        contact THUTOra for you.
      </p>
      <p>
        <strong>Stuck on your work?</strong> Ask THUTOra in the chat: it explains step by step.
      </p>
      <p className="help-urgent">
        <strong>If you're not safe, or something is worrying you,</strong> talk to a teacher or an adult you trust. You
        can call Childline free on <strong>116</strong>, any time. In an emergency, call the police on{" "}
        <strong>10111</strong>.
      </p>
      {contact && <p className="admin-screen__muted">THUTOra is run by Zynora Technologies.</p>}
    </div>
  );
}

function ParentHelp({ contact }) {
  return (
    <div className="help-simple">
      <p>
        <strong>Questions about your child's account, marks or notices?</strong> Please contact your child's school
        first. They manage logins and can see the full picture.
      </p>
      <p>
        <strong>Privacy concern, or the school can't help?</strong> Contact THUTOra support:
      </p>
      <ContactCard contact={contact} />
    </div>
  );
}

export default function HelpCentre({ token, product }) {
  const [open, setOpen] = useState(false);
  const [contact, setContact] = useState(null);
  const closeRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    if (!contact) fetchSupportContact().then(setContact).catch(() => {});
    closeRef.current?.focus();
    const onKey = (e) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, contact]);

  return (
    <>
      <button type="button" className="chat-screen__logout" onClick={() => setOpen(true)} title="Help and support">
        <LifeBuoy size={18} aria-hidden="true" />
        <span className="change-password__label">Help</span>
      </button>
      {open && (
        <div className="modal-backdrop" onClick={() => setOpen(false)}>
          <div
            className="modal-card help-centre"
            role="dialog"
            aria-modal="true"
            aria-label="Help and support"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="help-centre__head">
              <h2>Help and support</h2>
              <button ref={closeRef} type="button" onClick={() => setOpen(false)} aria-label="Close help">
                <X size={20} aria-hidden="true" />
              </button>
            </div>
            {STAFF.has(product) && <StaffHelp token={token} product={product} contact={contact} />}
            {product === "learn" && <LearnerHelp contact={contact} />}
            {product === "connect" && <ParentHelp contact={contact} />}
          </div>
        </div>
      )}
    </>
  );
}
