import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Alert, Spinner } from "@/components/ui/status";
import { api } from "@/lib/api";
import { sourceLabel } from "@/lib/github";
import type { AskResponse } from "@/types/api";

export function AskPanel({ repositoryFullName }: { repositoryFullName: string | null }) {
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AskResponse | null>(null);

  async function ask(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(
        await api<AskResponse>("/ask", {
          question,
          repository_full_name: repositoryFullName ?? undefined,
        }),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not get an answer.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <form onSubmit={ask} className="flex flex-col gap-3 sm:flex-row" aria-label="Ask a question">
        <label className="flex-1">
          <span className="sr-only">Question</span>
          <input
            required
            minLength={3}
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder={`Why did ${repositoryFullName ?? "the project"} make this choice?`}
            className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
          />
        </label>
        <Button type="submit" disabled={loading}>
          Ask
        </Button>
      </form>

      {loading && <Spinner label="Reading the discussions… the first answer can take 30 seconds" />}
      {error && <Alert tone="error">{error}</Alert>}

      {result?.status === "insufficient_evidence" && (
        <Alert tone="notice">
          Not enough evidence to answer. {result.limitations}
        </Alert>
      )}

      {result?.status === "answered" && (
        <article className="space-y-3 rounded-lg border border-slate-200 p-4">
          <p className="leading-7 text-slate-800">{result.answer}</p>
          {result.limitations && (
            <p className="text-sm text-slate-500">Limitations: {result.limitations}</p>
          )}
          <div>
            <h3 className="text-xs font-semibold uppercase text-slate-500">Sources</h3>
            <ol className="mt-1 space-y-1 text-sm">
              {result.citations.map((c, index) => (
                <li key={c.source_url}>
                  <span className="text-slate-500">[{index + 1}]</span>{" "}
                  <a href={c.source_url} target="_blank" rel="noreferrer" className="text-indigo-700 hover:underline">
                    {sourceLabel(c.source_url)}
                  </a>{" "}
                  <span className="text-slate-600">
                    {c.discussion_title}
                    {c.author && ` · ${c.author}`}
                  </span>
                </li>
              ))}
            </ol>
          </div>
        </article>
      )}
    </div>
  );
}
