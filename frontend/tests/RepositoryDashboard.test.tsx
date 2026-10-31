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
};

function serve(routes: Record<string, unknown>) {
  const fetchMock = vi.fn<typeof fetch>(async (input) => {
    const url = String(input);
    const body = routes[url.replace("/api/v1", "")];
    return new Response(JSON.stringify(body), { status: body ? 200 : 404 });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderDashboard(token = "") {
  const onSelect = vi.fn();
  render(<RepositoryDashboard token={token} refreshKey={0} selectedId={null} onSelect={onSelect} />);
  return onSelect;
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

  it("starts a sync with the pasted token and shows the reply", async () => {
    const fetchMock = serve({
      "/repositories": [repo],
      "/repositories/r1": repo,
      "/repositories/r1/sync": { repository_id: "r1", message: "Sync started" },
    });
    renderDashboard("ghp_test");

    fireEvent.click(await screen.findByRole("button", { name: "Sync" }));

    expect(await screen.findByText("Sync started")).toBeInTheDocument();
    const [, init] = fetchMock.mock.calls.find(([url]) => String(url).endsWith("/sync"))!;
    expect(JSON.parse(init?.body as string)).toEqual({ token: "ghp_test" });
  });

  it("selects a repository", async () => {
    serve({ "/repositories": [repo], "/repositories/r1": repo });
    const onSelect = renderDashboard();

    fireEvent.click(await screen.findByRole("button", { name: "Select" }));

    expect(onSelect).toHaveBeenCalledWith(repo);
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
