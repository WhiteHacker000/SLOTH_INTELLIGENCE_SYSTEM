import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "../src/App";

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
};

const routes: Record<string, unknown> = {
  "/repositories": [repo],
  "/repositories/r1": repo,
  "/repositories/r1/decisions": [decision],
};

const scrollIntoView = vi.fn();

beforeEach(() => {
  // jsdom has no layout, so scrolling is recorded instead of performed.
  Element.prototype.scrollIntoView = scrollIntoView;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const body = routes[String(input).replace("/api/v1", "")];
      return new Response(JSON.stringify(body), { status: 200 });
    }),
  );
});

afterEach(() => {
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
});
