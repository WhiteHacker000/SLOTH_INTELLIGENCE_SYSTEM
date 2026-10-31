import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AskPanel } from "../src/features/ask/AskPanel";

function respond(status: number, body: unknown) {
  const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status }));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function ask(question: string, repository: string | null = "pallets/blinker") {
  render(<AskPanel repositoryFullName={repository} />);
  fireEvent.change(screen.getByLabelText("Question"), { target: { value: question } });
  fireEvent.click(screen.getByRole("button", { name: "Ask" }));
}

afterEach(() => vi.unstubAllGlobals());

describe("AskPanel", () => {
  it("shows the answer with linked sources and asks within the repo", async () => {
    const fetchMock = respond(200, {
      question: "Why fix leaks?",
      status: "answered",
      answer: "Two dictionaries kept references alive.",
      citations: [
        {
          content: "…",
          source_url: "https://github.com/a/b/pull/12",
          discussion_number: 12,
          discussion_title: "Fixed memory leaks.",
          author: "Cykooz",
        },
      ],
      limitations: "Who approved it is not stated.",
    });
    ask("Why fix leaks?");

    expect(await screen.findByText("Two dictionaries kept references alive.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "PR #12" })).toHaveAttribute(
      "href",
      "https://github.com/a/b/pull/12",
    );
    expect(screen.getByText(/Fixed memory leaks. · Cykooz/)).toBeInTheDocument();
    expect(screen.getByText(/Who approved it is not stated/)).toBeInTheDocument();
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      question: "Why fix leaks?",
      repository_full_name: "pallets/blinker",
    });
  });

  it("says when there is not enough evidence", async () => {
    respond(200, {
      question: "Why Kubernetes?",
      status: "insufficient_evidence",
      answer: null,
      citations: [],
      limitations: "No discussion clearly covers this question.",
    });
    ask("Why Kubernetes?", null);

    expect(await screen.findByText(/Not enough evidence to answer/)).toBeInTheDocument();
  });

  it("shows when the model is unavailable", async () => {
    respond(503, { detail: "The answer model is not available" });
    ask("Why?");

    expect(await screen.findByRole("alert")).toHaveTextContent("The answer model is not available");
  });
});
