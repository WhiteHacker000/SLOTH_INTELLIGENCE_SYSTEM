import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ProjectHomePage } from "../src/pages/ProjectHomePage";

describe("ProjectHomePage", () => {
  it("labels planned capabilities and does not claim they are implemented", () => {
    render(<ProjectHomePage />);

    expect(
      screen.getByRole("heading", {
        name: "Open-Source Decision Intelligence and Knowledge Recovery",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("GitHub discussion ingestion")).toBeInTheDocument();
    expect(
      screen.getByText(/are not implemented yet/i),
    ).toBeInTheDocument();
  });
});
