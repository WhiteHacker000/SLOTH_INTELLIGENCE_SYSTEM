import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DecisionExplorer } from "../src/features/decisions/DecisionExplorer";
import { sourceLabel } from "../src/lib/github";

const decision = {
  id: "d1",
  title: "Drop 3.8",
  decision: "Stop supporting Python 3.8.",
  rationale: ["It reached end of life."],
  alternatives: [{ approach: "Keep 3.8", rejection_reason: "Extra CI work." }],
  evidence: [
    {
      excerpt: "3.8 goes end of life this month",
      source_url: "https://github.com/a/b/pull/12#issuecomment-99",
    },
  ],
  code: [],
};

function respond(status: number, body: unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status })),
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("DecisionExplorer", () => {
  it("shows decision, reasons, alternatives and evidence links", async () => {
    respond(200, [decision]);
    render(<DecisionExplorer repositoryId="r1" />);

    expect(await screen.findByText("Stop supporting Python 3.8.")).toBeInTheDocument();
    expect(screen.getByText("It reached end of life.")).toBeInTheDocument();
    expect(screen.getByText(/Keep 3.8 — not chosen: Extra CI work./)).toBeInTheDocument();
    expect(screen.getByText(/3.8 goes end of life this month/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "PR #12 comment on GitHub" })).toHaveAttribute(
      "href",
      decision.evidence[0].source_url,
    );
  });

  it("explains how to get decisions when there are none", async () => {
    respond(200, []);
    render(<DecisionExplorer repositoryId="r1" />);

    expect(await screen.findByText(/Extract decisions/)).toBeInTheDocument();
  });

  it("shows an error", async () => {
    respond(404, { detail: "Repository not found" });
    render(<DecisionExplorer repositoryId="r1" />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Repository not found");
  });
});

describe("sourceLabel", () => {
  it.each([
    ["https://github.com/a/b/issues/7", "Issue #7"],
    ["https://github.com/a/b/pull/8#discussion_r1", "PR #8 comment"],
    ["https://github.com/a/b/pull/8#pullrequestreview-5", "PR #8 review"],
    ["https://example.com", "GitHub"],
  ])("%s -> %s", (url, label) => {
    expect(sourceLabel(url)).toBe(label);
  });

  it("links the files and lines a decision touched, lines first", async () => {
    const files = Array.from({ length: 9 }, (_, i) => ({
      path: `src/f${i}.py`,
      line: null,
      url: `https://github.com/a/b/blob/main/src/f${i}.py`,
    }));
    const reviewed = { path: "src/cache.py", line: 42, url: "https://github.com/a/b/blob/abc/src/cache.py#L42" };
    respond(200, [{ ...decision, code: [...files, reviewed] }]);
    render(<DecisionExplorer repositoryId="r1" />);

    const line = await screen.findByRole("link", { name: "src/cache.py:42" });
    expect(line).toHaveAttribute("href", reviewed.url);
    const links = screen.getAllByRole("link").filter((a) => a.textContent?.startsWith("src/"));
    expect(links[0]).toBe(line);
    expect(links).toHaveLength(8);
    expect(screen.getByText("and 2 more files")).toBeInTheDocument();
  });

  it("leaves out the code section when no files are known", async () => {
    respond(200, [decision]);
    render(<DecisionExplorer repositoryId="r1" />);

    await screen.findByText("Stop supporting Python 3.8.");
    expect(screen.queryByText("Code")).not.toBeInTheDocument();
  });
});
