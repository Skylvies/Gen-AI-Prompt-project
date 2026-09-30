import { METRICS } from "../constants";

// Sliders are relative importance (0-100). The backend rescales them to add up to 100%.
export default function WeightsEditor({ weights, onChange }) {
  const total = METRICS.reduce((sum, m) => sum + (weights[m.key] || 0), 0);

  return (
    <div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {METRICS.map((m) => {
          const share = total ? Math.round((100 * (weights[m.key] || 0)) / total) : 0;
          return (
            <label key={m.key} className="block" title={m.hint}>
              <span className="flex items-baseline justify-between text-sm">
                <span className="font-medium text-slate-700">{m.label}</span>
                <span className="tabular-nums text-slate-500">{share}%</span>
              </span>
              <input
                type="range"
                min="0"
                max="100"
                step="5"
                value={weights[m.key] || 0}
                onChange={(e) => onChange({ ...weights, [m.key]: Number(e.target.value) })}
                className="mt-1 w-full accent-indigo-600"
              />
            </label>
          );
        })}
      </div>
      {total === 0 && <p className="mt-2 text-sm text-red-700">At least one weight must be above zero.</p>}
    </div>
  );
}
