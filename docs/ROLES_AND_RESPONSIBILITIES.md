# THUTOra — Roles and responsibilities

*23 Nov 2026. The full version, with each role's responsibilities, Zynora's
support rules, the onboarding steps and a diagram of who gives which role,
is the shared doc:
[THUTOra — Roles and Responsibilities](https://claude.ai/artifact/6AwgF92m4MrDG5g6TFVvNh).
Keep that doc and this summary in step when access rules change. The code is
the final word: `app/services/school_scope.py` (staff), ADR-031 (school roles),
ADR-039 (officials), ADR-043 (families), ADR-050 (support).*

**Rules everywhere:**
- Your own school only, and below your own role. Nobody changes their own role.
- Seeing a learner's name doesn't mean seeing their marks.
- Only Zynora creates a principal or an education official.
- No role in the app, staff included, can read a learner's tutor
  conversations.

| Role | Learner names | Marks and work | Manage accounts | Notices, consent, AI budget | Give roles | Support tickets | Given by |
|---|---|---|---|---|---|---|---|
| Learner | Self | Self (test marks once released) | Own password | No | No | No (asks a teacher) | School management |
| Family viewer | One child | That child's progress | Own password | No | No | No (asks the school) | A guardian of that child |
| Parent / guardian | Own children | Their progress | Own password; invites or removes viewers | No | No | No (asks the school) | The school, or SMS sign-up if allowed |
| Teacher | Own classes | Own classes, own subjects | Own learners' passwords, consent, guardian contacts | No | No | Own | School management |
| Departmental head | Department's grades | Department's subjects | As a teacher | No | No | Own | Principal or deputy |
| School admin | Whole school | **None** | Whole school | Yes | No | School's | Principal or deputy |
| Deputy principal | Whole school | Whole school | Whole school | Yes | Departmental head, school admin | School's | Principal |
| Principal | Whole school | Whole school | Whole school | Yes | Deputy, departmental head, school admin | School's | Zynora |
| Circuit / district official | No names | Totals for their area (groups under 5 learners hidden) | No | No | No | Own | Zynora |
| Province / national official (DoE head) | — | *Planned* | — | — | — | — | Zynora (planned) |
| THUTOra support (Zynora) | Only when a ticket or legal duty requires it | Same | Schools, principals, officials | No (the school's decision) | Principal, officials | Answers them | Zynora directors |

**Open gaps** (detail in the shared doc):
- province and national officials aren't built;
- support's script actions aren't in the activity log;
- there's no tool to remove an official or a principal role;
- the support "never" rules are policy, so they need to be in contracts;
- support is one person with every tool.
