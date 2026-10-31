const plannedCapabilities = [
  "GitHub discussion ingestion",
  "Decision extraction with source evidence",
  "Semantic search and cited answers",
];

export function ProjectHomePage() {
  return (
    <main className="mx-auto flex min-h-screen w-full max-w-5xl flex-col justify-center px-6 py-16">
      <p className="mb-4 text-sm font-semibold uppercase tracking-[0.18em] text-indigo-700">
        Project foundation
      </p>
      <h1 className="max-w-3xl text-4xl font-bold tracking-tight text-slate-950 sm:text-5xl">
        Open-Source Decision Intelligence and Knowledge Recovery
      </h1>
      <p className="mt-6 max-w-2xl text-lg leading-8 text-slate-600">
        Recover the reasoning behind technical decisions from the discussions
        that shaped open-source projects.
      </p>
      <section
        aria-labelledby="planned-heading"
        className="mt-12 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8"
      >
        <h2 id="planned-heading" className="text-xl font-semibold text-slate-900">
          Planned capabilities
        </h2>
        <ul className="mt-5 space-y-3 text-slate-700">
          {plannedCapabilities.map((capability) => (
            <li key={capability} className="flex items-start gap-3">
              <span
                aria-hidden="true"
                className="mt-2 size-2 shrink-0 rounded-full bg-indigo-600"
              />
              {capability}
            </li>
          ))}
        </ul>
        <p className="mt-6 border-t border-slate-100 pt-5 text-sm text-slate-500">
          This is a setup screen. Import, extraction, retrieval, and answers are
          not implemented yet.
        </p>
      </section>
    </main>
  );
}
