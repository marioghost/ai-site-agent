/** Answer strategies for Knowledge Profile topics — mirrors backend AnswerStrategy. */
export const ANSWER_STRATEGIES = [
  "overview",
  "fact",
  "list",
  "table",
  "contact",
  "pricing",
  "comparison",
  "step_by_step",
  "faq",
  "troubleshooting",
  "generic",
] as const;

export type AnswerStrategy = (typeof ANSWER_STRATEGIES)[number];
