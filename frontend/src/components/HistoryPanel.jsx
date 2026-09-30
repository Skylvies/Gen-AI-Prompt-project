import { useCallback, useEffect, useState } from "react";
import { api, exportUrl } from "../api";
import { TECHNIQUE_COLORS } from "../constants";

const linkBtn = "rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50";

export default function HistoryPanel({ onOpen }) {
  const [items, setItems] = useState(null);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    api.list().then(setItems).catch((e) => setError(e.message));
  }, []);
  useEffect(load, [load]);

  async function remove(id) {
    if (!window.confirm(`Delete experiment #${id}? This cannot be undone.`)) return;
    try {
      await api.remove(id);
      load();
    } catch (e) {
      setError(e.message);
    }
  }

  if (error) return <p role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">{error}</p>;
  if (!items) return <p className="text-slate-500">Loading history&hellip;</p>;

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-semibold">Experiment history <span className="text-sm font-normal text-slate-500">({items.length})</span></h2>
        {items.length > 0 && (
          <div className="flex gap-2">
            <a href={exportUrl("csv")} className={linkBtn}>Export all CSV</a>
            <a href={exportUrl("json")} className={linkBtn}>Export all JSON</a>
          </div>
        )}
      </div>

      {items.length === 0 ? (
        <p className="mt-6 text-center text-sm text-slate-500">No experiments yet. Run one from the Experiment tab.</p>
      ) : (
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
                <th className="py-2 pr-3">#</th>
                <th className="py-2 pr-3">When</th>
                <th className="py-2 pr-3">Mode</th>
                <th className="py-2 pr-3">Task</th>
                <th className="py-2 pr-3">Recommended</th>
                <th className="py-2 pr-3 text-right">Score</th>
                <th className="py-2" />
              </tr>
            </thead>
            <tbody>
              {items.map((e) => (
                <tr key={e.id} className="border-b border-slate-100">
                  <td className="py-2 pr-3 font-medium">{e.id}</td>
                  <td className="whitespace-nowrap py-2 pr-3 text-slate-600">{new Date(e.created_at).toLocaleString()}</td>
                  <td className="py-2 pr-3">
                    <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${e.mode === "demo" ? "bg-amber-100 text-amber-800" : "bg-sky-100 text-sky-800"}`}>
                      {e.mode === "demo" ? "Demo (simulated)" : `Real · ${e.model}`}
                    </span>
                  </td>
                  <td className="max-w-xs truncate py-2 pr-3" title={e.task}>{e.task}</td>
                  <td className="py-2 pr-3">
                    {e.recommended_technique ? (
                      <span className="inline-flex items-center gap-2">
                        <span className="h-2.5 w-2.5 rounded-full" style={{ background: TECHNIQUE_COLORS[e.recommended_technique] }} />
                        {e.recommended_technique.replace("_", "-")}
                      </span>
                    ) : "—"}
                  </td>
                  <td className="py-2 pr-3 text-right tabular-nums">{e.best_score?.toFixed(1) ?? "—"}</td>
                  <td className="whitespace-nowrap py-2 text-right">
                    <button onClick={() => onOpen(e.id)} className="mr-3 text-indigo-700 hover:underline">Open</button>
                    <a href={exportUrl("csv", e.id)} className="mr-3 text-slate-600 hover:underline">CSV</a>
                    <a href={exportUrl("json", e.id)} className="mr-3 text-slate-600 hover:underline">JSON</a>
                    <button onClick={() => remove(e.id)} className="text-red-700 hover:underline">Delete</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
