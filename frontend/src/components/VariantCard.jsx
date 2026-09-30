import { TECHNIQUE_COLORS, formatCost, formatMs } from "../constants";

const FLAG_LABELS = {
  unsupported_number: "Numbers not found in the task/reference",
  unsupported_name: "Names not found in the task/reference",
  citation_or_link: "Links or citation-style phrases",
  overconfident_wording: "Over-confident wording",
};

export default function VariantCard({ result: r, simulated }) {
  const checks = r.details?.validity_checks || [];
  const flags = r.details?.reliability_flags || [];
  const approx = r.tokens_estimated ? "~" : "";

  return (
    <article className={`rounded-xl border bg-white p-5 shadow-sm ${r.is_recommended ? "border-emerald-300" : "border-slate-200"}`}>
      <header className="flex flex-wrap items-center justify-between gap-2">
        <h4 className="flex items-center gap-2 font-semibold">
          <span className="h-3 w-3 rounded-full" style={{ background: TECHNIQUE_COLORS[r.technique] }} />
          {r.rank ? `#${r.rank} ` : ""}{r.label}
          {r.is_recommended && <span className="rounded bg-emerald-600 px-1.5 py-0.5 text-[10px] font-semibold text-white">RECOMMENDED</span>}
        </h4>
        <span className="text-sm text-slate-600">
          Overall <strong className="tabular-nums">{r.overall_score.toFixed(1)}</strong> / 100
        </span>
      </header>

      {r.error ? (
        <p role="alert" className="mt-3 rounded-md bg-red-50 p-3 text-sm text-red-800">This variant failed: {r.error}</p>
      ) : (
        <>
          <p className="mt-2 text-xs text-slate-500">
            {approx}{r.input_tokens} in + {approx}{r.output_tokens} out tokens &middot; {approx}{formatCost(r.cost_usd)} &middot;{" "}
            {formatMs(r.latency_ms)}{simulated ? " (simulated)" : ""} &middot; {r.details?.word_count} words &middot; finish: {r.details?.finish_reason}
          </p>
          <div className="mt-3">
            <h5 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Response</h5>
            <pre className="mt-1 max-h-72 overflow-auto whitespace-pre-wrap rounded-md bg-slate-50 p-3 text-sm text-slate-800">{r.response || "(empty)"}</pre>
          </div>
        </>
      )}

      <details className="mt-3">
        <summary className="cursor-pointer text-sm text-indigo-700">Prompt sent to the model</summary>
        <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap rounded-md bg-slate-50 p-3 text-xs text-slate-800">{r.prompt}</pre>
      </details>

      {!r.error && (
        <details className="mt-2">
          <summary className="cursor-pointer text-sm text-indigo-700">Why these scores? (checks and flags)</summary>
          <div className="mt-2 grid gap-4 text-sm md:grid-cols-2">
            <div>
              <h5 className="font-medium">Validity checks &middot; {r.validity.toFixed(0)}%</h5>
              <ul className="mt-1 space-y-1">
                {checks.map((c) => (
                  <li key={c.check} className={c.passed ? "text-emerald-700" : "text-red-700"}>
                    {c.passed ? "✓" : "✗"} {c.check}
                  </li>
                ))}
              </ul>
              <p className="mt-2 text-xs text-slate-500">
                Relevance method: {r.details?.relevance_method === "reference_overlap_f2" ? "overlap with your reference answer" : "coverage of the task's keywords"}
              </p>
            </div>
            <div>
              <h5 className="font-medium">Hallucination-risk flags &middot; reliability {r.reliability.toFixed(0)}/100</h5>
              {flags.length === 0 ? (
                <p className="mt-1 text-emerald-700">No risk signals found (this does not prove the answer is true).</p>
              ) : (
                <ul className="mt-1 space-y-1">
                  {flags.map((f) => (
                    <li key={f.type} className="text-amber-800">
                      −{f.penalty} {FLAG_LABELS[f.type]}: <span className="font-mono text-xs">{f.examples.join(", ")}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </details>
      )}
    </article>
  );
}
