// One colour per technique, reused in every chart so a variant looks the same everywhere.
export const TECHNIQUE_COLORS = {
  direct: "#6366f1",
  role: "#0ea5e9",
  few_shot: "#10b981",
  structured: "#f59e0b",
  constraint: "#ef4444",
  reasoning: "#8b5cf6",
};

// The seven metrics in the overall score (same keys as the backend).
export const METRICS = [
  { key: "relevance", label: "Relevance", hint: "Overlap with the reference answer (or with the task's keywords if none given). Heuristic." },
  { key: "validity", label: "Validity", hint: "Share of pass/fail checks passed: not empty, not truncated, not a refusal, required format." },
  { key: "reliability", label: "Reliability", hint: "Hallucination RISK indicator: 100 minus penalties for invented numbers, names, links, over-confident wording. Heuristic, not a fact-check." },
  { key: "conciseness", label: "Conciseness", hint: "100 up to the target length, then decreasing to 0 at 3x the target." },
  { key: "tokens", label: "Tokens", hint: "Fewer tokens is better. Normalised across the variants of this experiment." },
  { key: "cost", label: "Cost", hint: "Lower cost is better. Normalised across the variants of this experiment." },
  { key: "latency", label: "Latency", hint: "Lower response time is better. Normalised across the variants of this experiment." },
];

export const EXAMPLES = [
  { label: "Explain a concept", task: "Explain what overfitting is in machine learning." },
  {
    label: "Summarize text",
    task: "Summarize: The team shipped the new login page on Monday. Two bugs were found on Tuesday and fixed on Wednesday. Customer feedback has been positive.",
  },
  { label: "Classify sentiment", task: "Classify the sentiment of this review: 'The battery is great but the screen scratches easily.'" },
  { label: "Compare two ideas", task: "What is the difference between a process and a thread in an operating system?" },
];

export const formatCost = (usd) => `$${usd.toFixed(5)}`;
export const formatMs = (ms) => `${Math.round(ms).toLocaleString()} ms`;
export const toSliders = (weights) =>
  Object.fromEntries(METRICS.map((m) => [m.key, Math.round((weights[m.key] ?? 0) * 100)]));
