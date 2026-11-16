import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/status";
import { api, setAdminKey } from "@/lib/api";
import type { AdminStatus } from "@/types/api";

interface Props {
  onUnlocked: (status: AdminStatus) => void;
}

/** Lets the owner unlock import, sync and extract on a shared server. */
export function AdminKeyForm({ onUnlocked }: Props) {
  const [key, setKey] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setAdminKey(key);
    try {
      const status = await api<AdminStatus>("/admin");
      if (status.key_valid) {
        onUnlocked(status);
        return;
      }
      setError("That admin key is not right.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not check the key.");
    }
    setAdminKey("");
  }

  return (
    <form onSubmit={submit} className="mt-4 space-y-2" aria-label="Admin key">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <input
          type="password"
          autoComplete="off"
          aria-label="Admin key"
          value={key}
          onChange={(event) => setKey(event.target.value)}
          placeholder="Admin key, to import and extract"
          className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm sm:w-72"
        />
        <Button type="submit" variant="secondary" disabled={!key}>
          Unlock
        </Button>
      </div>
      {error && <Alert tone="error">{error}</Alert>}
    </form>
  );
}
