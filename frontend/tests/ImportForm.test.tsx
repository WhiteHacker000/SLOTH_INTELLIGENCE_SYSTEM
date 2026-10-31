import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ImportForm } from "../src/features/repositories/ImportForm";

function mockFetch(status: number, body: unknown) {
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(JSON.stringify(body), { status }),
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function submit(url: string, token = "") {
  const onRegistered = vi.fn();
  render(<ImportForm token={token} onTokenChange={vi.fn()} onRegistered={onRegistered} />);
  fireEvent.change(screen.getByLabelText("Public GitHub repository"), {
    target: { value: url },
  });
  fireEvent.click(screen.getByRole("button", { name: "Import" }));
  return onRegistered;
}

const registered = (message: string | null) => ({
  repository: { id: "1", full_name: "pallets/click" },
  estimate: { items: 4000, api_calls: 4200, token_recommended: !!message, message },
});

afterEach(() => vi.unstubAllGlobals());

describe("ImportForm", () => {
  it("registers a repository and sends the token only when given", async () => {
    const fetchMock = mockFetch(201, registered(null));
    const onRegistered = submit("pallets/click", "ghp_test");

    await vi.waitFor(() => expect(onRegistered).toHaveBeenCalled());
    const body = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(body).toEqual({ url: "pallets/click", token: "ghp_test" });
  });

  it("shows the notice when a token is recommended", async () => {
    mockFetch(201, registered("This repository is large. Add your GitHub token."));
    submit("pallets/click");

    expect(await screen.findByText(/Add your GitHub token/)).toBeInTheDocument();
  });

  it("shows validation errors in plain words", async () => {
    mockFetch(422, {
      detail: [{ msg: "Value error, Enter a GitHub repository like owner/name" }],
    });
    submit("gitlab.com/a/b");

    expect(await screen.findByRole("alert")).toHaveTextContent(
      /^Enter a GitHub repository like owner\/name$/,
    );
  });

  it("explains when the backend is down", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));
    submit("pallets/click");

    expect(await screen.findByRole("alert")).toHaveTextContent(/backend running/);
  });
});
