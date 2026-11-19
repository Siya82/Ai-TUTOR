/*
 * NEW 19 Nov 2026 (ADR-037, POPIA basics). The privacy notice shown from the
 * login screen and the learner's Settings. DRAFT for legal review: items in
 * [square brackets] must be filled in by Zynora before go-live. When the text
 * changes, bump PRIVACY_NOTICE_VERSION in backend/app/services/privacy.py so
 * new consents record which version was agreed to.
 */
import { useEffect } from "react";

export const PRIVACY_NOTICE_VERSION = "2026-11-19";

export default function PrivacyNotice({ onClose }) {
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="privacy-overlay" role="dialog" aria-modal="true" aria-labelledby="privacy-title">
      <div className="privacy-notice">
        <div className="privacy-notice__header">
          <h2 id="privacy-title">THUTOra privacy notice</h2>
          <button type="button" className="admin-screen__link-button" onClick={onClose}>
            Close
          </button>
        </div>
        <p className="admin-screen__muted">Version {PRIVACY_NOTICE_VERSION}</p>

        <h3>Who we are</h3>
        <p>
          THUTOra is provided by Zynora Technologies [registered name, registration number, address]. Your
          school decides to use THUTOra and is responsible for learners' information; Zynora processes it on the
          school's behalf. Information Officer: [name, email, phone].
        </p>

        <h3>What we collect</h3>
        <ul>
          <li>Learners: name, grade, school and student number, class.</li>
          <li>What learners do in THUTOra: questions asked, the tutor's answers, assignment answers and marks, and photos or files they upload.</li>
          <li>Settings such as preferred language.</li>
          <li>Staff: name, staff number, school roles and the classes and subjects they teach.</li>
          <li>Parent or guardian consent records (who gave consent, and when).</li>
        </ul>

        <h3>Why we use it</h3>
        <p>
          To tutor learners in the CAPS curriculum, mark their work, and show their teachers and school
          leaders how they are progressing, so they can help. We do not sell personal information or use it for
          advertising.
        </p>

        <h3>The AI tutor</h3>
        <p>
          Learners' questions, answers and uploaded images are sent to our AI provider, Anthropic, to produce the
          tutor's replies and marking. Anthropic processes this outside South Africa under contractual safeguards
          and does not use it to train its models [confirm against the current Anthropic commercial terms]. Learners
          should not put personal details such as ID numbers or addresses into their questions.
        </p>

        <h3>Children</h3>
        <p>
          Learners are children under the Protection of Personal Information Act (POPIA). The school records the
          consent of a parent or guardian before a learner uses THUTOra, and a parent or guardian may withdraw it
          at any time through the school.
        </p>

        <h3>How long we keep it</h3>
        <p>
          While the learner is at a school that uses THUTOra, and up to [12 months] after they leave or the school
          stops using THUTOra, after which it is deleted. A school can delete a learner's data at any time.
        </p>

        <h3>Your rights</h3>
        <p>
          You may ask the school to see the information held about you or your child, correct it, or delete it.
          The school can download a complete copy from THUTOra. You may also complain to the Information
          Regulator (South Africa): inforeg.org.za.
        </p>

        <h3>Security</h3>
        <p>
          Accounts are password protected, each school only sees its own learners, teachers only see the learners
          they teach, and information is stored [in South Africa] on access-controlled servers.
        </p>
      </div>
    </div>
  );
}
