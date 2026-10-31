import { useState } from "react";

import { ImportForm } from "@/features/repositories/ImportForm";

export default function App() {
  // The token lives only in memory and is sent with requests that need it.
  const [token, setToken] = useState("");
  const [added, setAdded] = useState<string | null>(null);

  return (
    <main className="mx-auto w-full max-w-5xl space-y-8 px-6 py-10">
      <header>
        <h1 className="text-3xl font-bold tracking-tight text-slate-950">
          Decision Intelligence
        </h1>
        <p className="mt-2 text-slate-600">
          Recover why an open-source project made its technical choices, with links
          to the original GitHub discussions.
        </p>
      </header>

      <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="mb-4 text-lg font-semibold text-slate-900">Import a repository</h2>
        <ImportForm
          token={token}
          onTokenChange={setToken}
          onRegistered={({ repository }) => setAdded(repository.full_name)}
        />
        {added && <p className="mt-4 text-sm text-slate-600">Added {added}.</p>}
      </section>
    </main>
  );
}
