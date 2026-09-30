export default function Header({ view, setView }) {
  const tab = (id, label) => (
    <button
      onClick={() => setView(id)}
      aria-current={view === id ? "page" : undefined}
      className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${
        view === id ? "bg-indigo-600 text-white" : "text-slate-600 hover:bg-slate-100"
      }`}
    >
      {label}
    </button>
  );

  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-4">
        <div>
          <h1 className="text-lg font-semibold sm:text-xl">Adaptive Prompt Optimization &amp; Evaluation Framework</h1>
          <p className="text-sm text-slate-500">Compare prompting techniques using measurable, transparent metrics</p>
        </div>
        <nav className="flex gap-1" aria-label="Main">
          {tab("lab", "Experiment")}
          {tab("history", "History")}
        </nav>
      </div>
    </header>
  );
}
