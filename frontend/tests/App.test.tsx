import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "../src/App";
import { setAdminKey } from "../src/lib/api";

const repo = {
  id: "r1",
  full_name: "pallets/click",
  html_url: "https://github.com/pallets/click",
  description: null,
  last_synced_at: null,
  last_sync_error: null,
  sync_status: "synced",
  created_at: "2026-01-01T00:00:00Z",
  discussion_count: 1,
  comment_count: 1,
  decision_count: 1,
  extracting: false,
};

const decision = {
  id: "d1",
  title: "Drop 3.8",
  decision: "Stop supporting Python 3.8.",
  rationale: ["End of life.", "End of life."],
  alternatives: [],
  evidence: [{ excerpt: "end of life", source_url: "https://github.com/pallets/click/pull/1" }],
  code: [],
};

let routes: Record<string, unknown>;

const openRoutes: Record<string, unknown> = {
  "/admin": { key_required: false, key_valid: true },
  "/auth/me": { sign_in_enabled: false, user: null },
  "/repositories": [repo],
  "/repositories/r1": repo,
  "/repositories/r1/decisions": [decision],
};

const scrollIntoView = vi.fn();

beforeEach(() => {
  routes = openRoutes;
  // jsdom has no layout, so scrolling is recorded instead of performed.
  Element.prototype.scrollIntoView = scrollIntoView;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input).replace("/api/v1", "");
      const key = new Headers(init?.headers).get("X-Admin-Key");
      const body = path === "/admin" && key === "secret" ? { key_required: true, key_valid: true } : routes[path];
      if (path === "/auth/logout") return new Response(null, { status: 204 });
      if (path === "/repositories/r1/extract") {
        return new Response(JSON.stringify({ detail: "Only maintainers can extract." }), { status: 403 });
      }
      return new Response(JSON.stringify(body), { status: 200 });
    }),
  );
});

afterEach(() => {
  setAdminKey("");
  vi.unstubAllGlobals();
  scrollIntoView.mockClear();
});

describe("App", () => {
  it("shows a hint until a repository is selected", async () => {
    render(<App />);

    expect(await screen.findByText("pallets/click")).toBeInTheDocument();
    expect(screen.getByText(/Select a repository above to see its decisions/)).toBeInTheDocument();
  });

  it("selecting scrolls to Ask and shows that repo's decisions", async () => {
    render(<App />);

    fireEvent.click(await screen.findByRole("button", { name: "Select" }));

    expect(scrollIntoView).toHaveBeenCalledWith({ behavior: "smooth", block: "start" });
    expect(screen.getByRole("heading", { name: "Ask about pallets/click" })).toBeInTheDocument();
    expect(await screen.findByText("Stop supporting Python 3.8.")).toBeInTheDocument();
    expect(screen.getAllByText("End of life.")).toHaveLength(2);

    fireEvent.click(screen.getByRole("button", { name: "Deselect" }));

    expect(screen.getByText(/Select a repository above/)).toBeInTheDocument();
    expect(scrollIntoView).toHaveBeenCalledTimes(1);
  });

  it("hides import until the right admin key is entered", async () => {
    routes = { ...openRoutes, "/admin": { key_required: true, key_valid: false } };
    render(<App />);

    const input = await screen.findByLabelText("Admin key", { selector: "input" });
    expect(screen.queryByText("Import a repository")).not.toBeInTheDocument();

    fireEvent.change(input, { target: { value: "wrong" } });
    fireEvent.click(screen.getByRole("button", { name: "Unlock" }));
    expect(await screen.findByText("That admin key is not right.")).toBeInTheDocument();

    fireEvent.change(input, { target: { value: "secret" } });
    fireEvent.click(screen.getByRole("button", { name: "Unlock" }));
    expect(await screen.findByText("Import a repository")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Unlock" })).not.toBeInTheDocument();
  });

  it("offers sign-in and keeps import hidden for visitors", async () => {
    routes = { ...openRoutes, "/auth/me": { sign_in_enabled: true, user: null } };
    render(<App />);

    const link = await screen.findByRole("link", { name: "Sign in with GitHub" });
    expect(link).toHaveAttribute("href", "/api/v1/auth/login");
    expect(screen.queryByText("Import a repository")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Admin key", { selector: "input" })).not.toBeInTheDocument();
  });

  it("lets a signed-in user import with their own token and sign out", async () => {
    routes = {
      ...openRoutes,
      "/auth/me": { sign_in_enabled: true, user: { login: "octo", avatar_url: null } },
    };
    render(<App />);

    expect(await screen.findByText("Import a repository")).toBeInTheDocument();
    expect(screen.getByText("octo")).toBeInTheDocument();
    expect(screen.queryByText("GitHub token (optional)")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Extract decisions" }));
    expect(await screen.findByText("Only maintainers can extract.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
    expect(await screen.findByRole("link", { name: "Sign in with GitHub" })).toBeInTheDocument();
    expect(screen.queryByText("Import a repository")).not.toBeInTheDocument();
  });
});
