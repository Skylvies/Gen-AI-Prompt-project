import {
  Bar, BarChart, CartesianGrid, Legend, PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar, RadarChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { TECHNIQUE_COLORS } from "../constants";

const RADAR_AXES = [
  ["relevance", "Relevance"],
  ["validity", "Validity"],
  ["reliability", "Reliability"],
  ["conciseness", "Conciseness"],
  ["tokens_score", "Tokens"],
  ["cost_score", "Cost"],
  ["latency_score", "Latency"],
];

function Panel({ title, note, children }) {
  return (
    <div className="rounded-lg border border-slate-200 p-3">
      <h4 className="text-sm font-medium text-slate-700">{title}</h4>
      {note && <p className="text-xs text-slate-500">{note}</p>}
      <div className="mt-2 h-64">{children}</div>
    </div>
  );
}

function SimpleBar({ data, dataKey, unit = "", digits = 0 }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="name" tick={{ fontSize: 11 }} interval={0} angle={-25} textAnchor="end" height={60} />
        <YAxis tick={{ fontSize: 11 }} width={48} />
        <Tooltip formatter={(v) => `${Number(v).toFixed(digits)}${unit}`} />
        <Bar dataKey={dataKey} radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export default function Charts({ rows }) {
  const ok = rows.filter((r) => !r.error);
  if (ok.length === 0) return <p className="mt-2 text-sm text-slate-500">No successful variants to chart.</p>;

  const bars = ok.map((r) => ({
    name: r.label,
    fill: TECHNIQUE_COLORS[r.technique],
    overall: r.overall_score,
    tokens: r.total_tokens,
    latency: Math.round(r.latency_ms),
    cost: Number(r.cost_usd.toFixed(6)),
  }));

  const radar = RADAR_AXES.map(([key, label]) => ({
    metric: label,
    ...Object.fromEntries(ok.map((r) => [r.technique, r[key]])),
  }));

  return (
    <div className="mt-3 space-y-4">
      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="Overall weighted score (0–100)">
          <SimpleBar data={bars} dataKey="overall" digits={1} />
        </Panel>
        <Panel title="Metric profile" note="Efficiency axes (tokens, cost, latency) are relative to the other variants.">
          <ResponsiveContainer width="100%" height="100%">
            <RadarChart data={radar} outerRadius="70%">
              <PolarGrid />
              <PolarAngleAxis dataKey="metric" tick={{ fontSize: 11 }} />
              <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
              {ok.map((r) => (
                <Radar key={r.technique} name={r.label} dataKey={r.technique} stroke={TECHNIQUE_COLORS[r.technique]}
                  fill={TECHNIQUE_COLORS[r.technique]} fillOpacity={0.1} />
              ))}
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Tooltip />
            </RadarChart>
          </ResponsiveContainer>
        </Panel>
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <Panel title="Total tokens (input + output)"><SimpleBar data={bars} dataKey="tokens" /></Panel>
        <Panel title="Response latency (ms)"><SimpleBar data={bars} dataKey="latency" unit=" ms" /></Panel>
        <Panel title="Cost (USD)"><SimpleBar data={bars} dataKey="cost" unit=" USD" digits={5} /></Panel>
      </div>
    </div>
  );
}
