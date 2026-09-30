import { useState } from "react";

export default function RecommendationCard({ experiment }) {
  const [copied, setCopied] = useState(false);
  const winner = experiment.results.find((r) => r.is_recommended);

  if (!winner) {
    return (
      <section className="rounded-xl border border-red-200 bg-red-50 p-5 text-sm text-red-800">
        <strong>No recommendation.</strong> Every prompt variant failed. Check the error messages below.
      </section>
    );
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(winner.prompt);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard not available (e.g. insecure context) - the text is still selectable */
    }
  }

  return (
    <section className="rounded-xl border border-emerald-200 bg-emerald-50 p-5 shadow-sm">
      <p className="text-xs font-semibold uppercase tracking-wide text-emerald-700">Recommended prompt</p>
      <h3 className="mt-1 text-2xl font-semibold text-emerald-950">
        {winner.label} <span className="text-base font-medium text-emerald-800">&middot; {winner.overall_score.toFixed(1)} / 100</span>
      </h3>
      <p className="mt-2 text-sm text-emerald-900">{experiment.recommendation_reason}</p>
      <pre className="mt-3 max-h-56 overflow-auto whitespace-pre-wrap rounded-md bg-white p-3 text-xs text-slate-800 ring-1 ring-emerald-200">
        {winner.prompt}
      </pre>
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <button onClick={copy} className="rounded-md bg-emerald-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-800">
          {copied ? "Copied" : "Copy prompt"}
        </button>
        <p className="text-xs text-emerald-900">
          &ldquo;Best&rdquo; means highest weighted score under <em>your</em> weights, on this one task
          {experiment.simulated ? ", using simulated responses" : ", from a single run per variant"}. It is not a universal ranking.
        </p>
      </div>
    </section>
  );
}
