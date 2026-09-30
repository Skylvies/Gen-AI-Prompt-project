import { TECHNIQUE_COLORS } from "../constants";

export default function PromptPreview({ variants }) {
  return (
    <div className="grid gap-4 md:grid-cols-2">
      {variants.map((v) => (
        <div key={v.technique} className="rounded-lg border border-slate-200 bg-white p-4">
          <div className="flex items-center gap-2">
            <span className="h-3 w-3 rounded-full" style={{ background: TECHNIQUE_COLORS[v.technique] }} />
            <h4 className="font-semibold">{v.label}</h4>
          </div>
          <p className="mt-1 text-sm text-slate-500">{v.description}</p>
          <pre className="mt-3 max-h-64 overflow-auto whitespace-pre-wrap rounded-md bg-slate-50 p-3 text-xs text-slate-800">
            {v.prompt}
          </pre>
        </div>
      ))}
    </div>
  );
}
