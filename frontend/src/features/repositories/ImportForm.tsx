import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Alert, Spinner } from "@/components/ui/status";
import { api } from "@/lib/api";
import type { RepositoryRegistered } from "@/types/api";

interface Props {
  token: string;
  onTokenChange: (token: string) => void;
  onRegistered: (result: RepositoryRegistered) => void;
}

export function ImportForm({ token, onTokenChange, onRegistered }: Props) {
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    setNotice(null);
    try {
      const result = await api<RepositoryRegistered>("/repositories", {
        url,
        token: token || undefined,
      });
      setNotice(result.estimate.message);
      setUrl("");
      onRegistered(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-3" aria-label="Import repository">
      <div className="flex flex-col gap-3 sm:flex-row">
        <label className="flex-1">
          <span className="mb-1 block text-sm font-medium text-slate-700">
            Public GitHub repository
          </span>
          <input
            required
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            placeholder="https://github.com/pallets/click or pallets/click"
            className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
          />
        </label>
        <label className="sm:w-64">
          <span className="mb-1 block text-sm font-medium text-slate-700">
            GitHub token (optional)
          </span>
          <input
            type="password"
            autoComplete="off"
            value={token}
            onChange={(event) => onTokenChange(event.target.value)}
            placeholder="Only kept in this tab"
            className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
          />
        </label>
      </div>
      <div className="flex items-center gap-3">
        <Button type="submit" disabled={loading}>
          Import
        </Button>
        {loading && <Spinner label="Checking repository…" />}
      </div>
      {error && <Alert tone="error">{error}</Alert>}
      {notice && <Alert tone="notice">{notice}</Alert>}
    </form>
  );
}
