import { METRICS, TECHNIQUE_COLORS, formatCost } from "../constants";

const hint = (key) => METRICS.find((m) => m.key === key)?.hint;

const COLUMNS = [
  { key: "overall_score", label: "Overall", best: "max", show: (v) => v.toFixed(1) },
  { key: "relevance", label: "Relevance", best: "max", show: (v) => v.toFixed(1), title: hint("relevance") },
  { key: "validity", label: "Validity", best: "max", show: (v) => v.toFixed(1), title: hint("validity") },
  { key: "reliability", label: "Reliability*", best: "max", show: (v) => v.toFixed(1), title: hint("reliability") },
  { key: "conciseness", label: "Conciseness", best: "max", show: (v) => v.toFixed(1), title: hint("conciseness") },
  { key: "total_tokens", label: "Tokens", best: "min", show: (v, r) => `${r.tokens_estimated ? "~" : ""}${v}`, title: hint("tokens") },
  { key: "cost_usd", label: "Cost", best: "min", show: (v, r) => `${r.tokens_estimated ? "~" : ""}${formatCost(v)}`, title: hint("cost") },
  { key: "latency_ms", label: "Latency (ms)", best: "min", show: (v) => Math.round(v).toLocaleString(), title: hint("latency") },
];

export default function MetricsTable({ experiment, rows }) {
  const ok = rows.filter((r) => !r.error);
  const bestValue = (col) => {
    if (ok.length < 2) return null;
    const values = ok.map((r) => r[col.key]);
    return col.best === "max" ? Math.max(...values) : Math.min(...values);
  };

  return (
    <div className="mt-3">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[760px] text-left text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
              <th className="py-2 pr-3">Rank</th>
              <th className="py-2 pr-3">Technique</th>
              {COLUMNS.map((c) => (
                <th key={c.key} className="py-2 pr-3 text-right" title={c.title}>{c.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className={`border-b border-slate-100 ${r.is_recommended ? "bg-emerald-50/60" : ""}`}>
                <td className="py-2 pr-3 font-medium">{r.rank ?? "—"}</td>
                <td className="py-2 pr-3">
                  <span className="inline-flex items-center gap-2">
                    <span className="h-2.5 w-2.5 rounded-full" style={{ background: TECHNIQUE_COLORS[r.technique] }} />
                    {r.label}
                    {r.is_recommended && <span className="rounded bg-emerald-600 px-1.5 py-0.5 text-[10px] font-semibold text-white">BEST</span>}
                    {r.error && <span className="rounded bg-red-600 px-1.5 py-0.5 text-[10px] font-semibold text-white">FAILED</span>}
                  </span>
                </td>
                {COLUMNS.map((c) => {
                  const isBest = !r.error && bestValue(c) === r[c.key];
                  return (
                    <td key={c.key} className={`py-2 pr-3 text-right tabular-nums ${isBest ? "font-semibold text-emerald-700" : ""}`}>
                      {c.show(r[c.key], r)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-3 text-xs text-slate-500">
        Green = best value in that column. Quality metrics are 0&ndash;100 (higher is better). *Reliability is a heuristic
        hallucination-<em>risk</em> indicator, not a fact-check.
        {experiment.simulated
          ? " Demo Mode: tokens and cost are estimates (~) and latency is simulated."
          : " Tokens and latency are measured from the API; cost = tokens × the configured price per million tokens."}
        {" "}Latency is a single measurement and varies between runs.
      </p>
    </div>
  );
}
