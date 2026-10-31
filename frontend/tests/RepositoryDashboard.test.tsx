import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RepositoryDashboard } from "../src/features/repositories/RepositoryDashboard";

const repo = {
  id: "r1",
  full_name: "pallets/click",
  html_url: "https://github.com/pallets/click",
  description: null,
  last_synced_at: null,
  last_sync_error: "GitHub rate limit reached. Add a token and sync again.",
  sync_status: "paused",
  created_at: "2026-01-01T00:00:00Z",
  discussion_count: 12,
  comment_count: 30,
  decision_count: 4,
  extracting: false,
};

type Route = unknown | (() => unknown);

function serve(routes: Record<string, Route>) {
  const fetchMock = vi.fn<typeof fetch>(async (input) => {
    const url = String(input);
    const route = routes[url.replace("/api/v1", "")];
    const body = typeof route === "function" ? route() : route;
    return new Response(JSON.stringify(body), { status: body ? 200 : 404 });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderDashboard(token = "", selectedId: string | null = null) {
  const onSelect = vi.fn();
  render(<RepositoryDashboard token={token} refreshKey={0} selectedId={selectedId} onSelect={onSelect} />);
  return onSelect;
}

/** Returns `running` once, then `done`, like the server during a job. */
function sequence(running: object, done: object) {
  let calls = 0;
  return () => (calls++ === 0 ? { ...repo, ...running } : { ...repo, ...done });
}

afterEach(() => vi.unstubAllGlobals());

describe("RepositoryDashboard", () => {
  it("shows status, counts and the last sync error", async () => {
    serve({ "/repositories": [repo], "/repositories/r1": repo });
    renderDashboard();

    expect(await screen.findByText("pallets/click")).toHaveAttribute("href", repo.html_url);
    expect(screen.getByText("paused")).toBeInTheDocument();
    expect(screen.getByText(/12 discussions · 30 comments · 4 decisions/)).toBeInTheDocument();
    expect(screen.getByText(/rate limit reached/)).toBeInTheDocument();
  });

  it("shows a sync running and then completed, sending the pasted token", async () => {
    let started = false;
    const status = sequence({ sync_status: "running" }, { sync_status: "synced" });
    const fetchMock = serve({
      "/repositories": [repo],
      "/repositories/r1": () => (started ? status() : repo),
      "/repositories/r1/sync": () => {
        started = true;
        return { repository_id: "r1", message: "Sync started" };
      },
    });
    vi.useFakeTimers({ shouldAdvanceTime: true });
    renderDashboard("ghp_test");

    fireEvent.click(await screen.findByRole("button", { name: "Sync" }));
    expect(await screen.findByText("Syncing…")).toBeInTheDocument();
    await vi.advanceTimersByTimeAsync(5000);

    expect(await screen.findByText("Sync completed")).toBeInTheDocument();
    vi.useRealTimers();
    const [, init] = fetchMock.mock.calls.find(([url]) => String(url).endsWith("/sync"))!;
    expect(JSON.parse(init?.body as string)).toEqual({ token: "ghp_test" });
  });

  it("shows extraction finishing with the number of new decisions", async () => {
    let started = false;
    const status = sequence({ extracting: true }, { decision_count: 9 });
    serve({
      "/repositories": [repo],
      "/repositories/r1": () => (started ? status() : repo),
      "/repositories/r1/extract": () => {
        started = true;
        return { repository_id: "r1", threads: 15, message: "Extraction started" };
      },
    });
    vi.useFakeTimers({ shouldAdvanceTime: true });
    renderDashboard();

    fireEvent.click(await screen.findByRole("button", { name: "Extract decisions" }));
    expect(await screen.findByText("Extracting decisions…")).toBeInTheDocument();
    await vi.advanceTimersByTimeAsync(5000);

    expect(await screen.findByText("Extraction completed · 5 new decisions")).toBeInTheDocument();
    vi.useRealTimers();
  });

  it("selects a repository, and deselects it when clicked again", async () => {
    serve({ "/repositories": [repo], "/repositories/r1": repo });
    const onSelect = renderDashboard("", "r1");

    fireEvent.click(await screen.findByRole("button", { name: "Deselect" }));

    expect(onSelect).toHaveBeenCalledWith(null);
  });

  it("shows an empty state", async () => {
    serve({ "/repositories": [] });
    renderDashboard();

    expect(await screen.findByText(/No repositories yet/)).toBeInTheDocument();
  });

  it("shows an error when the list cannot load", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));
    renderDashboard();

    expect(await screen.findByRole("alert")).toHaveTextContent(/backend running/);
  });
});
