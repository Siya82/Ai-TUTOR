/*
 * NEW 23 Nov 2026 (ADR-050). Help Centre guides. Short, task-shaped, and
 * worded with the exact labels on screen -- update a guide whenever the
 * screen it describes changes. `products` says where a guide is shown.
 */

export const GUIDES = [
  // --- TEACH ---------------------------------------------------------------
  {
    id: "reset-password",
    products: ["teach", "admin"],
    title: "A learner can't log in",
    steps: [
      "Open the Students tab (in ADMIN: Learners → All learners).",
      "Find the learner and click Reset password.",
      "Give the learner the temporary password shown. They choose their own new password the next time they log in.",
      "If the account was switched off, Reset password isn't shown: click Reactivate first.",
    ],
  },
  {
    id: "create-assignment",
    products: ["teach"],
    title: "Set practice or a test",
    steps: [
      "Open the Assignments tab.",
      "Choose the topic, then pick questions from the question bank, or use Or write a new question with its model answer.",
      "Choose Practice (AI feedback shows right away) or Test (results are withheld until you release them).",
      "Under Assign to, choose the class or learners.",
      "Click Create assignment.",
      "For a test, open it after the due date and click Release results to students.",
    ],
  },
  {
    id: "check-answers",
    products: ["teach"],
    title: "Check answers and change a mark",
    steps: [
      "Open the Assignments tab and the assignment.",
      "Click View answers next to a learner.",
      "Each answer shows THUTOra's mark. Change it to correct or incorrect and add a note if you disagree. Your mark replaces THUTOra's.",
      "If a learner asked THUTOra about a test question while the test was open, you'll see a notice at the top. The tutor coaches without giving answers.",
    ],
  },
  {
    id: "report-question",
    products: ["teach"],
    title: "A question or model answer is wrong",
    steps: [
      "In View answers, click Report this question under the question.",
      "Say what's wrong, then Send report.",
      "Zynora checks it and fixes or hides the question for every school.",
    ],
  },
  {
    id: "today",
    products: ["teach"],
    title: "Using the Today page",
    steps: [
      "Today shows the learners who need help, the ones who've gone quiet, and the topics your classes find hardest.",
      "Next to a weak topic, click Send practice to give a short practice set to just the learners who struggled.",
    ],
  },
  // --- ADMIN ---------------------------------------------------------------
  {
    id: "add-learners",
    products: ["admin"],
    title: "Add learners",
    steps: [
      "Open Learners.",
      "Add a learner: type their details and create the login.",
      "Bulk upload: upload a CSV file to create many learners at once. The screen shows the columns it expects and reports any rows it couldn't use.",
      "Hand each learner their login number and temporary password.",
    ],
  },
  {
    id: "classes-staff",
    products: ["admin"],
    title: "Set up classes and teachers",
    steps: [
      "Classes: click Create class, then add the learners in it.",
      "Staff: click Create login for each teacher.",
      "On a teacher's card, click Allocate subjects / grades and choose their subject and classes. A teacher sees only the learners they're allocated.",
      "Use Give a role for principals, deputies, departmental heads and school admins.",
    ],
  },
  {
    id: "notices",
    products: ["admin"],
    title: "Send a notice to parents",
    steps: [
      "Open Notices.",
      "Write the title and message, and choose which grade it's for.",
      "Tick the acknowledgement box if parents must confirm they've read it.",
      "Click Post notice. The list shows how many parents have acknowledged it.",
    ],
  },
  {
    id: "privacy-ai",
    products: ["admin"],
    title: "Consent and the AI budget",
    steps: [
      "Open School settings → Privacy and AI use.",
      "Require recorded consent: learners without a consent record can't use the AI tutor (everything else still works).",
      "Monthly AI budget: a limit in US dollars for the school's tutor use. When it's used up, the tutor pauses until the next month and teachers mark answers instead.",
    ],
  },
  {
    id: "activity",
    products: ["admin"],
    title: "See who changed what",
    steps: [
      "Open Activity to see sensitive actions: password resets, accounts switched off, roles given, learners deleted or exported.",
    ],
  },
  // --- INSIGHTS ------------------------------------------------------------
  {
    id: "insights-bands",
    products: ["insights"],
    title: "Reading INSIGHTS",
    steps: [
      "Each school shows participation, accuracy and a band: Good, Watch or Concern.",
      "Use the circuit buttons to look at one circuit at a time.",
      "Schools with very few learners show Too few learners, to protect learners' privacy.",
    ],
  },
  // --- everyone -------------------------------------------------------------
  {
    id: "topic-videos",
    products: ["teach", "admin", "insights"],
    title: "Topic induction videos",
    steps: [
      "When a learner opens a topic for the first time, a Starting … card offers a short video: what the topic is about, what to expect, what it builds on, and two worked examples.",
      "Learners can turn the voice-over off with Voice off; every word is also on screen.",
    ],
  },
  {
    id: "password",
    products: ["teach", "admin", "insights"],
    title: "Change your own password",
    steps: ["Click Password at the top of the screen, enter your current password and your new one."],
  },
];

export function guidesFor(product) {
  return GUIDES.filter((g) => g.products.includes(product));
}
