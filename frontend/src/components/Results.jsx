import { useState } from "react";
import { api, exportUrl } from "../api";
import { toSliders } from "../constants";
import Charts from "./Charts";
import MetricsTable from "./MetricsTable";
import RecommendationCard from "./RecommendationCard";
import VariantCard from "./VariantCard";
import WeightsEditor from "./WeightsEditor";

export default function Results({ experiment, onUpdated }) {
  const [weights, setWeights] = useState(toSliders(experiment.weights));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const ranked = [...experiment.results].sort((a, b) => (a.rank ?? 99) - (b.rank ?? 99));
  const total = Object.values(weights).reduce((a, b) => a + b, 0);

  async function rescore() {
    setBusy(true);
    setError("");
    try {
      onUpdated(await api.rescore(experiment.id, weights));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">Results &mdash; experiment #{experiment.id}</h2>
          <p className="text-sm text-slate-500">
            {experiment.simulated ? (
              <span className="rounded bg-amber-100 px-1.5 py-0.5 font-medium text-amber-800">SIMULATED (Demo Mode)</span>
            ) : (
              <span className="rounded bg-sky-100 px-1.5 py-0.5 font-medium text-sky-800">REAL &middot; {experiment.model}</span>
            )}{" "}
            &middot; {new Date(experiment.created_at).toLocaleString()}
          </p>
        </div>
        <div className="flex gap-2">
          <a href={exportUrl("csv", experiment.id)} className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50">
            Export CSV
          </a>
          <a href={exportUrl("json", experiment.id)} className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50">
            Export JSON
          </a>
        </div>
      </div>

      <p className="rounded-lg bg-white p-3 text-sm text-slate-700 shadow-sm ring-1 ring-slate-200">
        <span className="font-medium">Task:</span> {experiment.task}
      </p>

      <RecommendationCard experiment={experiment} />

      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h3 className="font-semibold">Metric comparison</h3>
        <MetricsTable experiment={experiment} rows={ranked} />
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h3 className="font-semibold">Charts</h3>
        <Charts rows={ranked} />
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h3 className="font-semibold">Change the weights and re-score</h3>
        <p className="mb-4 text-sm text-slate-500">
          Re-scoring reuses the stored responses and measurements &mdash; no new API calls, no extra cost.
        </p>
        <WeightsEditor weights={weights} onChange={setWeights} />
        <div className="mt-4 flex items-center gap-3">
          <button
            onClick={rescore}
            disabled={busy || total === 0}
            className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            {busy ? "Re-scoring…" : "Re-score with these weights"}
          </button>
          {error && <span className="text-sm text-red-700">{error}</span>}
        </div>
      </section>

      <section>
        <h3 className="mb-3 font-semibold">Prompts and responses</h3>
        <div className="space-y-4">
          {ranked.map((r) => (
            <VariantCard key={r.id} result={r} simulated={experiment.simulated} />
          ))}
        </div>
      </section>
    </div>
  );
}
