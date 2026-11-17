import { useEffect, useState } from "react";

import { Alert, Spinner } from "@/components/ui/status";
import { api } from "@/lib/api";
import { sourceLabel } from "@/lib/github";
import type { Decision } from "@/types/api";

const REFRESH_MS = 10000;
// Large PRs touch many files; the first few are enough to orient a reader.
const MAX_FILES = 8;

function CodeLinks({ code }: { code: Decision["code"] }) {
  // Exact lines first: they say the most about where the decision lives.
  const sorted = [...code].sort((a, b) => Number(b.line !== null) - Number(a.line !== null));
  const hidden = sorted.length - MAX_FILES;
  return (
    <div className="mt-3">
      <h4 className="text-xs font-semibold uppercase text-slate-500">Code</h4>
      <ul className="mt-1 flex flex-wrap gap-2">
        {sorted.slice(0, MAX_FILES).map((c) => (
          <li key={c.path}>
            <a
              href={c.url}
              target="_blank"
              rel="noreferrer"
              className="rounded bg-slate-100 px-2 py-0.5 font-mono text-xs text-slate-800 hover:bg-slate-200"
            >
              {c.line ? `${c.path}:${c.line}` : c.path}
            </a>
          </li>
        ))}
      </ul>
      {hidden > 0 && <p className="mt-1 text-xs text-slate-500">and {hidden} more files</p>}
    </div>
  );
}

export function DecisionExplorer({ repositoryId }: { repositoryId: string }) {
  const [decisions, setDecisions] = useState<Decision[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    const load = () =>
      api<Decision[]>(`/repositories/${repositoryId}/decisions`).then(
        (list) => {
          if (!active) return;
          setDecisions(list);
          setError(null);
        },
        (err: unknown) => {
          if (active) setError(err instanceof Error ? err.message : "Could not load decisions.");
        },
      );
    load();
    // New decisions appear while an extraction is running.
    const timer = setInterval(load, REFRESH_MS);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [repositoryId]);

  if (error) return <Alert tone="error">{error}</Alert>;
  if (decisions === null) return <Spinner label="Loading decisions…" />;
  if (decisions.length === 0) {
    return (
      <p className="text-sm text-slate-600">
        No decisions yet. Click "Extract decisions" on the repository above.
      </p>
    );
  }

  return (
    <ul className="space-y-4">
      {decisions.map((d) => (
        <li key={d.id} className="rounded-lg border border-slate-200 p-4">
          <h3 className="font-semibold text-slate-900">{d.decision}</h3>
          {d.rationale.length > 0 && (
            <div className="mt-3">
              <h4 className="text-xs font-semibold uppercase text-slate-500">Why</h4>
              <ul className="mt-1 list-disc pl-5 text-sm text-slate-700">
                {d.rationale.map((reason, i) => (
                  <li key={i}>{reason}</li>
                ))}
              </ul>
            </div>
          )}
          {d.alternatives.length > 0 && (
            <div className="mt-3">
              <h4 className="text-xs font-semibold uppercase text-slate-500">Alternatives</h4>
              <ul className="mt-1 list-disc pl-5 text-sm text-slate-700">
                {d.alternatives.map((alt, i) => (
                  <li key={i}>
                    {alt.approach}
                    {alt.rejection_reason && ` — not chosen: ${alt.rejection_reason}`}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {d.code.length > 0 && <CodeLinks code={d.code} />}
          <div className="mt-3">
            <h4 className="text-xs font-semibold uppercase text-slate-500">Evidence</h4>
            <ul className="mt-1 space-y-2">
              {d.evidence.map((e, i) => (
                <li key={i} className="text-sm">
                  <blockquote className="border-l-2 border-slate-300 pl-3 text-slate-700">
                    "{e.excerpt}"
                  </blockquote>
                  <a href={e.source_url} target="_blank" rel="noreferrer" className="pl-3 text-indigo-700 hover:underline">
                    {sourceLabel(e.source_url)} on GitHub
                  </a>
                </li>
              ))}
            </ul>
          </div>
        </li>
      ))}
    </ul>
  );
}
