import { useCallback, useEffect, useState } from "react";

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

interface Props {
  token: string;
  refreshKey: number;
  selectedId: string | null;
  onSelect: (repository: RepositoryDetail) => void;
}

async function loadDetails(): Promise<RepositoryDetail[]> {
  const repositories = await api<Repository[]>("/repositories");
  return Promise.all(repositories.map((r) => api<RepositoryDetail>(`/repositories/${r.id}`)));
}

export function RepositoryDashboard({ token, refreshKey, selectedId, onSelect }: Props) {
  const [repositories, setRepositories] = useState<RepositoryDetail[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const refresh = useCallback(() => {
    loadDetails().then(
      (list) => {
        setRepositories(list);
        setError(null);
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

  async function start(path: string, body?: unknown) {
    setMessage(null);
    try {
      const job = await api<StartedJob>(path, body ?? {});
      setMessage(job.message);
      refresh();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Could not start.");
    }
  }

  if (error) return <Alert tone="error">{error}</Alert>;
  if (repositories === null) return <Spinner label="Loading repositories…" />;
  if (repositories.length === 0) {
    return <p className="text-sm text-slate-600">No repositories yet. Import one above.</p>;
  }

  return (
    <div className="space-y-3">
      {message && <Alert tone="notice">{message}</Alert>}
      <ul className="divide-y divide-slate-200 rounded-lg border border-slate-200">
        {repositories.map((repo) => (
          <li
            key={repo.id}
            className={cn("flex flex-wrap items-center gap-4 p-4", repo.id === selectedId && "bg-indigo-50")}
          >
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <a href={repo.html_url} target="_blank" rel="noreferrer" className="font-medium text-slate-900 hover:underline">
                  {repo.full_name}
                </a>
                <span className={cn("rounded-full px-2 py-0.5 text-xs font-medium", statusStyles[repo.sync_status])}>
                  {repo.sync_status.replace("_", " ")}
                </span>
              </div>
              <p className="mt-1 text-sm text-slate-600">
                {repo.discussion_count} discussions · {repo.comment_count} comments ·{" "}
                {repo.decision_count} decisions
                {repo.last_synced_at && ` · synced ${new Date(repo.last_synced_at).toLocaleString()}`}
              </p>
              {repo.last_sync_error && <p className="mt-1 text-sm text-red-700">{repo.last_sync_error}</p>}
            </div>
            <div className="flex gap-2">
              <Button
                variant="secondary"
                disabled={repo.sync_status === "running"}
                onClick={() => start(`/repositories/${repo.id}/sync`, { token: token || undefined })}
              >
                Sync
              </Button>
              <Button variant="secondary" onClick={() => start(`/repositories/${repo.id}/extract`)}>
                Extract decisions
              </Button>
              <Button onClick={() => onSelect(repo)}>Select</Button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
