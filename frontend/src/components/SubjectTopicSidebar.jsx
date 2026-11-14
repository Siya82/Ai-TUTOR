/*
 * Left-pane subject/topic navigator. NEW 14 Nov 2026, replacing the
 * Subject/Topic dropdowns (SubjectPicker.jsx/TopicPicker.jsx) -- Siya's
 * own usability concern after live testing: a student can forget a
 * dropdown exists at all and never open it, but a list that's already
 * sitting in view the whole time doesn't depend on them remembering
 * to. Each subject is grouped with its own grade; its topic list
 * expands underneath it.
 *
 * UPDATED 14 Nov 2026: turned into an accordion (only one subject's
 * topic list open at a time) -- Siya's own follow-up concern that
 * showing every topic for every subject at once would overflow the
 * pane once more subjects/topics are seeded (Grade 12 is next).
 * Clicking a subject's header toggles it open/closed; clicking it the
 * first time also jumps the active selection to its first topic (the
 * same "pick a subject, land on topic 1" behaviour the old dropdown
 * had), but merely re-opening or collapsing the already-active subject
 * doesn't change what's selected.
 *
 * SubjectPicker.jsx/TopicPicker.jsx are left in the codebase, just
 * unused, rather than deleted -- an easy revert if neither layout
 * holds up (REBUILD_SPEC.md's usual "don't delete, just stop wiring it
 * in" discipline).
 */

import { useEffect, useState } from "react";

export default function SubjectTopicSidebar({
  subjects,
  topics,
  selectedSubjectId,
  selectedTopicId,
  onSelectTopic,
  disabled,
}) {
  const orderedSubjects = [...subjects].sort(
    (a, b) => a.grade - b.grade || a.name.localeCompare(b.name)
  );

  const [expandedSubjectId, setExpandedSubjectId] = useState(selectedSubjectId);

  // Follows the active subject if it changes from elsewhere (e.g. the
  // default subject loading in once subjects/topics finish fetching).
  useEffect(() => {
    if (selectedSubjectId) setExpandedSubjectId(selectedSubjectId);
  }, [selectedSubjectId]);

  const toggleSubject = (subjectId, firstTopicId) => {
    if (subjectId === expandedSubjectId) {
      setExpandedSubjectId(null); // collapse -- doesn't change what's selected
      return;
    }
    setExpandedSubjectId(subjectId);
    if (subjectId !== selectedSubjectId) {
      onSelectTopic(subjectId, firstTopicId);
    }
  };

  return (
    <nav className="subject-sidebar">
      <div className="subject-sidebar__heading">Subjects &amp; Topics</div>
      {orderedSubjects.map((subject) => {
        const subjectTopics = topics.filter((t) => t.subject_id === subject.id);
        const isActiveSubject = subject.id === selectedSubjectId;
        const isExpanded = subject.id === expandedSubjectId;
        return (
          <div key={subject.id} className="subject-group">
            <button
              type="button"
              className={
                "subject-group__header" + (isActiveSubject ? " subject-group__header--active" : "")
              }
              onClick={() => toggleSubject(subject.id, subjectTopics[0]?.id ?? null)}
              disabled={disabled}
              aria-expanded={isExpanded}
            >
              <span className="subject-group__caret">{isExpanded ? "▾" : "▸"}</span>{" "}
              {subject.name} <span className="subject-group__grade">(Grade {subject.grade})</span>
            </button>
            {isExpanded && (
              <ul className="subject-group__topics">
                {subjectTopics.map((topic) => (
                  <li key={topic.id}>
                    <button
                      type="button"
                      className={
                        "topic-item" + (topic.id === selectedTopicId ? " topic-item--active" : "")
                      }
                      onClick={() => onSelectTopic(subject.id, topic.id)}
                      disabled={disabled}
                    >
                      {topic.name}
                    </button>
                  </li>
                ))}
                {subjectTopics.length === 0 && <li className="subject-group__empty">No topics yet</li>}
              </ul>
            )}
          </div>
        );
      })}
    </nav>
  );
}
