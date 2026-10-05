import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Api } from "./api";
import { Download, Pagination, RenderBoundary, SourceStatus } from "./ui";
import { health } from "./test/fixtures";

describe("shared analyst controls", () => {
  it("paginates with bounded previous/next controls", async () => {
    const move = vi.fn();
    const user = userEvent.setup();
    const { rerender } = render(
      <Pagination
        page={{ items: [1, 2], total: 4, limit: 2, offset: 0 }}
        offset={0}
        setOffset={move}
      />,
    );
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Next" }));
    expect(move).toHaveBeenLastCalledWith(2);
    rerender(
      <Pagination
        page={{ items: [3, 4], total: 4, limit: 2, offset: 2 }}
        offset={2}
        setOffset={move}
      />,
    );
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Previous" }));
    expect(move).toHaveBeenLastCalledWith(0);
  });
  it("downloads the requested saved resource and reports failed export errors", async () => {
    const api = new Api();
    const user = userEvent.setup();
    const exportRequest = vi
      .spyOn(api, "download")
      .mockRejectedValueOnce(new Error("network"))
      .mockResolvedValueOnce();
    render(
      <Download api={api} path="/api/portfolio" name="portfolio.json">
        Export portfolio
      </Download>,
    );
    await user.click(screen.getByRole("button", { name: "Export portfolio" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Could not reach",
    );
    await user.click(screen.getByRole("button", { name: "Export portfolio" }));
    expect(exportRequest).toHaveBeenLastCalledWith(
      "/api/portfolio",
      "portfolio.json",
    );
  });
  it("shows channel freshness and explicitly discloses a common publisher", async () => {
    const user = userEvent.setup();
    render(
      <SourceStatus
        health={{
          ...health,
          sources: health.sources.map((source) => ({
            ...source,
            stale: false,
            last_success_at: "2026-10-05T00:00:00Z",
            next_allowed_at: "2026-10-05T00:05:00Z",
          })),
        }}
      />,
    );
    await user.click(screen.getByText("Source status"));
    expect(screen.getByText("Live sources fresh")).toBeInTheDocument();
    expect(
      screen.getByText(/not independent confirmation/),
    ).toBeInTheDocument();
    expect(screen.getAllByText(/Next refresh allowed:/)).toHaveLength(2);
  });
  it("fails closed with a safe message when an incomplete financial response cannot render", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    const Broken = () => {
      throw new Error("private internal failure");
    };
    render(
      <RenderBoundary>
        <Broken />
      </RenderBoundary>,
    );
    expect(screen.getByRole("alert")).toHaveTextContent(
      "do not interpret an incomplete financial result",
    );
    expect(
      screen.queryByText("private internal failure"),
    ).not.toBeInTheDocument();
  });
});
