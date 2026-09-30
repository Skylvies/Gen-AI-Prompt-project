import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import Header from "./components/Header";
import ModeBanner from "./components/ModeBanner";
import TaskForm from "./components/TaskForm";
import Results from "./components/Results";
import HistoryPanel from "./components/HistoryPanel";

export default function App() {
  const [config, setConfig] = useState(null);
  const [configError, setConfigError] = useState("");
  const [view, setView] = useState("lab"); // "lab" | "history"
  const [mode, setMode] = useState("demo");
  const [experiment, setExperiment] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const loadConfig = useCallback(() => {
    setConfigError("");
    api.config().then(setConfig).catch((e) => setConfigError(e.message));
  }, []);
  useEffect(loadConfig, [loadConfig]);

  async function runExperiment(payload, accessCode) {
    setBusy(true);
    setError("");
    try {
      setExperiment(await api.run(payload, accessCode));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function openExperiment(id) {
    try {
      const data = await api.get(id);
      setExperiment(data);
      setError("");
      setView("lab");
    } catch (e) {
      setError(e.message);
      setView("lab");
    }
  }

  return (
    <div className="min-h-screen text-slate-900">
      <Header view={view} setView={setView} />
      <main className="mx-auto max-w-7xl space-y-6 px-4 py-6">
        {!config ? (
          <div className="rounded-xl border border-slate-200 bg-white p-8 text-center">
            {configError ? (
              <>
                <p className="font-medium text-red-700">{configError}</p>
                <button onClick={loadConfig} className="mt-4 rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700">
                  Retry
                </button>
              </>
            ) : (
              <p className="text-slate-600">
                Connecting to the server&hellip; <span className="text-slate-400">(free hosting can take up to a minute to wake up)</span>
              </p>
            )}
          </div>
        ) : view === "history" ? (
          <HistoryPanel onOpen={openExperiment} />
        ) : (
          <>
            <ModeBanner mode={mode} config={config} />
            <TaskForm config={config} busy={busy} onRun={runExperiment} onModeChange={setMode} />
            {busy && (
              <div role="status" className="rounded-xl border border-indigo-200 bg-indigo-50 p-4 text-sm text-indigo-800">
                Running the prompt variants&hellip; in Real mode this makes one API call per variant and can take 10&ndash;60 seconds.
              </div>
            )}
            {error && (
              <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
                {error}
              </div>
            )}
            {experiment && <Results key={experiment.id} experiment={experiment} onUpdated={setExperiment} />}
          </>
        )}
      </main>
      <footer className="mx-auto max-w-7xl px-4 pb-8 text-xs text-slate-500">
        All quality metrics are heuristics (see the README &ldquo;Limitations&rdquo;). Demo Mode output is simulated and is not evidence about any real model.
      </footer>
    </div>
  );
}
