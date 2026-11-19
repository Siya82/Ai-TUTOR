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
 *
 * UPDATED 14 Nov 2026 (Siya's own navigation request, ahead of the
 * Grade 12 scale-up that's about to roughly double the subject count):
 * grouped into visible "Grade N" sections instead of a flat list with
 * the grade as a small inline suffix on each subject button -- with 6
 * subject rows already (3 subjects x 2 grades) and 9 coming once
 * Grade 12 lands, a flat list stops being scannable at a glance.
 * Grades are sorted ascending, and subjects within a grade are sorted
 * alphabetically by name (so Accounting, then Physical Sciences, then
 * Pure Mathematics) -- the same (grade, name) ordering this component
 * already used internally, just rendered as actual section headings
 * now rather than left for the eye to group on its own.
 */

import { useMemo, useState } from "react";

export default function SubjectTopicSidebar({
  subjects,
  topics,
  selectedSubjectId,
  selectedTopicId,
  onSelectTopic,
  disabled,
}) {
  const gradeGroups = useMemo(() => {
    const byGrade = new Map();
    for (const subject of subjects) {
      if (!byGrade.has(subject.grade)) byGrade.set(subject.grade, []);
      byGrade.get(subject.grade).push(subject);
    }
    return [...byGrade.entries()]
      .sort(([gradeA], [gradeB]) => gradeA - gradeB)
      .map(([grade, subjectsInGrade]) => [
        grade,
        [...subjectsInGrade].sort((a, b) => a.name.localeCompare(b.name)),
      ]);
  }, [subjects]);

  const [expandedSubjectId, setExpandedSubjectId] = useState(selectedSubjectId);

  // Follows the active subject if it changes from elsewhere (e.g. the
  // default subject loading in once subjects/topics finish fetching).
  // Code review #17: adjusted during render (React's recommended pattern
  // for state derived from a prop) instead of in an effect.
  const [followedSubjectId, setFollowedSubjectId] = useState(selectedSubjectId);
  if (selectedSubjectId !== followedSubjectId) {
    setFollowedSubjectId(selectedSubjectId);
    if (selectedSubjectId) setExpandedSubjectId(selectedSubjectId);
  }

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
      {gradeGroups.map(([grade, subjectsInGrade]) => (
        <div key={grade} className="subject-sidebar__grade-group">
          <div className="subject-sidebar__grade-heading">Grade {grade}</div>
          {subjectsInGrade.map((subject) => {
            const subjectTopics = topics.filter((t) => t.subject_id === subject.id);
            const isActiveSubject = subject.id === selectedSubjectId;
            const isExpanded = subject.id === expandedSubjectId;
            return (
              <div key={subject.id} className="subject-group">
                <button
                  type="button"
                  className={
                    "subject-group__header" +
                    (isActiveSubject ? " subject-group__header--active" : "")
                  }
                  onClick={() => toggleSubject(subject.id, subjectTopics[0]?.id ?? null)}
                  disabled={disabled}
                  aria-expanded={isExpanded}
                >
                  <span className="subject-group__caret">{isExpanded ? "▾" : "▸"}</span>{" "}
                  {subject.name}
                </button>
                {isExpanded && (
                  <ul className="subject-group__topics">
                    {subjectTopics.map((topic, i) => [
                      // ADR-046: "Physics (Paper 1)" / "Chemistry (Paper 2)" headings
                      topic.section && topic.section !== subjectTopics[i - 1]?.section && (
                        <li key={`section-${topic.section}`} className="subject-group__section">
                          {topic.section}
                        </li>
                      ),
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
                      </li>,
                    ])}
                    {subjectTopics.length === 0 && (
                      <li className="subject-group__empty">No topics yet</li>
                    )}
                  </ul>
                )}
              </div>
            );
          })}
        </div>
      ))}
    </nav>
  );
}
