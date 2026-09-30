import { useState } from "react";
import { api } from "../api";
import { EXAMPLES, TECHNIQUE_COLORS, toSliders } from "../constants";
import PromptPreview from "./PromptPreview";
import WeightsEditor from "./WeightsEditor";

const inputClass =
  "mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500";

export default function TaskForm({ config, busy, onRun, onModeChange }) {
  const [task, setTask] = useState("");
  const [reference, setReference] = useState("");
  const [mode, setMode] = useState("demo");
  const [techniques, setTechniques] = useState(config.techniques.map((t) => t.key));
  const [targetWords, setTargetWords] = useState(100);
  const [weights, setWeights] = useState(toSliders(config.default_weights));
  const [accessCode, setAccessCode] = useState("");
  const [preview, setPreview] = useState(null);
  const [previewError, setPreviewError] = useState("");

  const weightTotal = Object.values(weights).reduce((a, b) => a + b, 0);
  const canRun = task.trim().length >= 3 && techniques.length >= 2 && weightTotal > 0 && !busy;

  const toggleTechnique = (key) =>
    setTechniques((cur) => (cur.includes(key) ? cur.filter((k) => k !== key) : [...cur, key]));

  const chooseMode = (value) => {
    setMode(value);
    onModeChange(value);
  };

  async function showPreview() {
    setPreviewError("");
    try {
      setPreview(await api.preview(task.trim(), techniques, Number(targetWords)));
    } catch (e) {
      setPreview(null);
      setPreviewError(e.message);
    }
  }

  function submit(e) {
    e.preventDefault();
    if (!canRun) return;
    onRun(
      {
        task: task.trim(),
        reference_answer: reference.trim() || null,
        mode,
        techniques,
        weights,
        target_words: Number(targetWords),
      },
      accessCode
    );
  }

  const modeButton = (value, label, disabled = false, title = "") => (
    <button
      type="button"
      disabled={disabled}
      title={title}
      onClick={() => chooseMode(value)}
      className={`px-4 py-1.5 text-sm font-medium transition first:rounded-l-md last:rounded-r-md ${
        mode === value ? "bg-indigo-600 text-white" : "bg-white text-slate-700 hover:bg-slate-50"
      } ${disabled ? "cursor-not-allowed opacity-50" : ""}`}
    >
      {label}
    </button>
  );

  return (
    <form onSubmit={submit} className="space-y-5 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-base font-semibold">1. Describe the task</h2>
        <div className="flex items-center gap-3">
          <span className="text-sm text-slate-600">Mode</span>
          <div className="inline-flex divide-x divide-slate-300 overflow-hidden rounded-md border border-slate-300">
            {modeButton("demo", "Demo")}
            {modeButton("real", "Real (API)", !config.real_available, config.real_unavailable_reason ? `Real mode unavailable: ${config.real_unavailable_reason}` : "")}
          </div>
        </div>
      </div>

      <div>
        <label htmlFor="task" className="text-sm font-medium text-slate-700">Task or prompt</label>
        <textarea
          id="task"
          rows={3}
          maxLength={2000}
          value={task}
          onChange={(e) => setTask(e.target.value)}
          placeholder="e.g. Explain what overfitting is in machine learning."
          className={inputClass}
        />
        <div className="mt-2 flex flex-wrap gap-2">
          {EXAMPLES.map((ex) => (
            <button
              type="button"
              key={ex.label}
              onClick={() => setTask(ex.task)}
              className="rounded-full border border-slate-300 px-3 py-1 text-xs text-slate-600 hover:bg-slate-50"
            >
              {ex.label}
            </button>
          ))}
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <div className="md:col-span-2">
          <label htmlFor="reference" className="text-sm font-medium text-slate-700">
            Reference answer <span className="font-normal text-slate-400">(optional &mdash; makes Relevance more meaningful)</span>
          </label>
          <textarea
            id="reference"
            rows={2}
            maxLength={2000}
            value={reference}
            onChange={(e) => setReference(e.target.value)}
            className={inputClass}
          />
        </div>
        <div>
          <label htmlFor="target" className="text-sm font-medium text-slate-700">Target length (words)</label>
          <input
            id="target"
            type="number"
            min="10"
            max="1000"
            value={targetWords}
            onChange={(e) => setTargetWords(e.target.value)}
            className={inputClass}
          />
          <p className="mt-1 text-xs text-slate-500">Answers longer than this lose Conciseness points.</p>
        </div>
      </div>

      <fieldset>
        <legend className="text-sm font-medium text-slate-700">2. Prompting techniques to compare (pick at least 2)</legend>
        <div className="mt-2 flex flex-wrap gap-2">
          {config.techniques.map((t) => {
            const on = techniques.includes(t.key);
            return (
              <label
                key={t.key}
                className={`flex cursor-pointer items-center gap-2 rounded-full border px-3 py-1.5 text-sm ${
                  on ? "border-indigo-400 bg-indigo-50 text-indigo-900" : "border-slate-300 text-slate-600"
                }`}
              >
                <input type="checkbox" checked={on} onChange={() => toggleTechnique(t.key)} className="sr-only" />
                <span className="h-2.5 w-2.5 rounded-full" style={{ background: TECHNIQUE_COLORS[t.key] }} />
                {t.label}
              </label>
            );
          })}
        </div>
      </fieldset>

      <details className="rounded-lg border border-slate-200 p-4">
        <summary className="cursor-pointer text-sm font-medium text-slate-700">3. Scoring weights (how much each metric matters)</summary>
        <div className="mt-4">
          <WeightsEditor weights={weights} onChange={setWeights} />
          <button
            type="button"
            onClick={() => setWeights(toSliders(config.default_weights))}
            className="mt-3 text-sm text-indigo-700 hover:underline"
          >
            Reset to defaults
          </button>
        </div>
      </details>

      {mode === "real" && config.real_requires_access_code && (
        <div className="max-w-sm">
          <label htmlFor="code" className="text-sm font-medium text-slate-700">Access code (required for Real mode)</label>
          <input
            id="code"
            type="password"
            autoComplete="off"
            value={accessCode}
            onChange={(e) => setAccessCode(e.target.value)}
            className={inputClass}
          />
        </div>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <button
          type="submit"
          disabled={!canRun}
          className="rounded-md bg-indigo-600 px-5 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {busy ? "Running…" : "Run experiment"}
        </button>
        <button
          type="button"
          disabled={task.trim().length < 3 || techniques.length < 1}
          onClick={showPreview}
          className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
        >
          Preview prompts (no LLM call)
        </button>
        {preview && (
          <button type="button" onClick={() => setPreview(null)} className="text-sm text-slate-500 hover:underline">
            Hide preview
          </button>
        )}
      </div>
      {previewError && <p className="text-sm text-red-700">{previewError}</p>}
      {preview && <PromptPreview variants={preview} />}
    </form>
  );
}
