import { useCallback, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Alert, Spinner } from "@/components/ui/status";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { Repository, RepositoryDetail, StartedJob, SyncStatus } from "@/types/api";

const REFRESH_MS = 5000;

const statusStyles: Record<SyncStatus, string> = {
  never_synced: "bg-slate-100 text-slate-700",
  running: "bg-blue-100 text-blue-800",
  paused: "bg-amber-100 text-amber-900",
  failed: "bg-red-100 text-red-800",
  synced: "bg-green-100 text-green-800",
};

const syncNotes: Partial<Record<SyncStatus, string>> = {
  synced: "Sync completed",
  paused: "Sync paused",
  failed: "Sync failed",
};

type Job = { kind: "sync" } | { kind: "extract"; decisionsBefore: number };

interface Props {
  token: string;
  refreshKey: number;
  selectedId: string | null;
  onSelect: (repository: RepositoryDetail | null) => void;
}

async function loadDetails(): Promise<RepositoryDetail[]> {
  const repositories = await api<Repository[]>("/repositories");
  return Promise.all(repositories.map((r) => api<RepositoryDetail>(`/repositories/${r.id}`)));
}

/** The note to show once a job the user started has finished, or null if still running. */
function finishedNote(job: Job, repo: RepositoryDetail): string | null {
  if (job.kind === "sync") {
    return repo.sync_status === "running" ? null : (syncNotes[repo.sync_status] ?? null);
  }
  if (repo.extracting) return null;
  return `Extraction completed · ${repo.decision_count - job.decisionsBefore} new decisions`;
}

export function RepositoryDashboard({ token, refreshKey, selectedId, onSelect }: Props) {
  const [repositories, setRepositories] = useState<RepositoryDetail[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notes, setNotes] = useState<Record<string, string>>({});
  // Jobs started from this page, so we can say when each one finishes.
  const jobs = useRef<Record<string, Job>>({});

  const refresh = useCallback(() => {
    loadDetails().then(
      (list) => {
        setRepositories(list);
        setError(null);
        const finished: Record<string, string> = {};
        for (const repo of list) {
          const job = jobs.current[repo.id];
          const note = job && finishedNote(job, repo);
          if (note) {
            finished[repo.id] = note;
            delete jobs.current[repo.id];
          }
        }
        if (Object.keys(finished).length) setNotes((old) => ({ ...old, ...finished }));
      },
      (err: unknown) =>
        setError(err instanceof Error ? err.message : "Could not load repositories."),
    );
  }, []);

  useEffect(() => {
    refresh();
    // Keeps counts and status moving while a sync or extraction runs.
    const timer = setInterval(refresh, REFRESH_MS);
    return () => clearInterval(timer);
  }, [refresh, refreshKey]);

  async function start(repo: RepositoryDetail, job: Job, path: string, body: unknown) {
    setNotes((old) => ({ ...old, [repo.id]: "" }));
    try {
      const reply = await api<StartedJob & { threads?: number }>(path, body);
      if (reply.threads === 0) {
        setNotes((old) => ({ ...old, [repo.id]: reply.message }));
      } else {
        jobs.current[repo.id] = job;
      }
      refresh();
    } catch (err) {
      setNotes((old) => ({ ...old, [repo.id]: err instanceof Error ? err.message : "Could not start." }));
    }
  }

  if (error) return <Alert tone="error">{error}</Alert>;
  if (repositories === null) return <Spinner label="Loading repositories…" />;
  if (repositories.length === 0) {
    return <p className="text-sm text-slate-600">No repositories yet. Import one above.</p>;
  }

  return (
    <ul className="divide-y divide-slate-200 rounded-lg border border-slate-200">
      {repositories.map((repo) => {
        const selected = repo.id === selectedId;
        const syncing = repo.sync_status === "running";
        return (
          <li
            key={repo.id}
            className={cn(
              "flex flex-wrap items-center gap-4 p-4",
              selected && "bg-indigo-50/70 ring-1 ring-inset ring-indigo-200",
            )}
          >
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <a href={repo.html_url} target="_blank" rel="noreferrer" className="font-medium text-slate-900 hover:underline">
                  {repo.full_name}
                </a>
                <span className={cn("rounded-full px-2 py-0.5 text-xs font-medium", statusStyles[repo.sync_status])}>
                  {repo.sync_status.replace("_", " ")}
                </span>
                {selected && <span className="text-xs font-medium text-indigo-700">Selected</span>}
              </div>
              <p className="mt-1 text-sm text-slate-600">
                {repo.discussion_count} discussions · {repo.comment_count} comments ·{" "}
                {repo.decision_count} decisions
                {repo.last_synced_at && ` · synced ${new Date(repo.last_synced_at).toLocaleString()}`}
              </p>
              {repo.last_sync_error && <p className="mt-1 text-sm text-red-700">{repo.last_sync_error}</p>}
              <div className="mt-1 text-sm">
                {syncing && <Spinner label="Syncing…" />}
                {repo.extracting && <Spinner label="Extracting decisions…" />}
                {!syncing && !repo.extracting && notes[repo.id] && (
                  <span className="text-green-700">{notes[repo.id]}</span>
                )}
              </div>
            </div>
            <div className="flex gap-2">
              <Button
                variant="secondary"
                disabled={syncing}
                onClick={() => start(repo, { kind: "sync" }, `/repositories/${repo.id}/sync`, { token: token || undefined })}
              >
                Sync
              </Button>
              <Button
                variant="secondary"
                disabled={repo.extracting}
                onClick={() =>
                  start(repo, { kind: "extract", decisionsBefore: repo.decision_count }, `/repositories/${repo.id}/extract`, {})
                }
              >
                Extract decisions
              </Button>
              <Button variant={selected ? "secondary" : "primary"} onClick={() => onSelect(selected ? null : repo)}>
                {selected ? "Deselect" : "Select"}
              </Button>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
