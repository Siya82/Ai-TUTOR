# ADR-050 — THUTOra support: Help Centre and tickets

**Date:** 23 Nov 2026 · **Status:** Accepted

## Context

THUTOra had no way for people to ask for help: no contact details, no
ticket, no guides. The pieces that did exist covered errors and content:
- crash reports (`/client-errors`);
- question reports;
- teacher password resets.

Siya set the support contacts:
- **support@zynoratech.co.za**;
- **WhatsApp +27 67 590 1165**, until a business number is set up;
- **06:00–18:00**.

## Decision

**Schools support their learners and parents; Zynora supports schools.**
Learners are minors, and under POPIA the school is the responsible party and
Zynora its operator. So:
- **Staff and officials** (role `teacher`, which includes principals and school
  admins, and `official`) can log tickets in the app.
- **Learners** are told to ask their teacher. Their Help screen also shows
  Childline 116 and police 10111.
- **Parents** are told to contact the school first. Their Help screen gives
  Zynora's contact details for privacy concerns, or when the school can't help.
- The login page says the same, with Zynora's contact details for schools and
  staff.

**In the app.** A **Help** button sits next to Password in every product, and
opens the Help Centre. For staff it has three parts:
- **Guides:** short, searchable, using the exact screen labels
  (`frontend/src/help/guides.js`).
- **Contact support:** category, summary, details, and "a class can't work
  right now". It asks for no learner names or ID numbers. Choosing
  safeguarding shows 10111 / Childline and "follow your school's process
  first".
- **My tickets:** the conversation, reply, and mark as resolved. School
  managers (principal, deputy, school admin) see every ticket from their school.

**Priority** comes from the category:
- **Urgent (p1):** outage, safeguarding, data/privacy.
- **Class blocked (p2):** any other category with the "a class can't work"
  box ticked.
- **Normal (p3):** how-to, bug, content, account, billing.
- **Suggestion (p4):** ideas.

Targets, within 06:00–18:00: P1 1 hour, P2 4 hours, P3 next working day,
P4 reviewed weekly.

**Statuses.** `open` means it's Zynora's turn, `waiting_on_school` means the
school's turn, then `resolved`. A school reply reopens a ticket.

**Zynora's side.** `python -m scripts.support` with `list`, `show`, `reply`
(`--resolve`) and `priority`. It works like the registration and
question-report scripts, which suits a one-person team; a web queue can come
later.
- Every new ticket and every school reply alerts the support mailbox by SMTP,
  if `SMTP_HOST` is set, and otherwise logs a WARNING.
- Urgent tickets also log at ERROR, so Cloud Error Reporting alerts even
  without email.
- Start-up logs how many tickets are waiting.

**Limits and privacy.**
- 10 tickets per user per day.
- The context sent with a ticket is the screen path, app version and role,
  never learner data.
- Resolved tickets are deleted after `RETENTION_SUPPORT_DAYS` (0 = keep) by
  `scripts/retention.py`.

**Data.** Migration 0025 adds `support_tickets` (with a short `number`
people can quote on WhatsApp) and `support_messages`.

## Later
- A business WhatsApp number, set with `SUPPORT_WHATSAPP`.
- A web support queue for Zynora staff once there's more than one person
  answering.
- A status page.
- An email to the ticket's author when Zynora replies. Staff logins have no
  email address yet, so they see replies in the app.
