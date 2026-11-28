// @vitest-environment jsdom

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom/vitest";

import JobDetails from "./JobDetails";

const apiFetch = vi.fn();

vi.mock("../api", () => ({
  apiFetch: (...args) => apiFetch(...args),
}));

function mockResponse(data, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => data,
  };
}

function details(jobOverrides = {}, match = { match_explanation: "Direct skill matches include Python." }) {
  return {
    job: {
      job_id: 2,
      source: "adzuna",
      title: "Data Analyst",
      company: "Example Corp",
      location: "Portland, OR",
      description: "Analyze data with Python and SQL...",
      job_url: "https://example.com/jobs/2",
      ...jobOverrides,
    },
    match,
  };
}

function renderDetails(onBack = vi.fn()) {
  render(<JobDetails jobId={2} onBack={onBack} />);
  return onBack;
}

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  cleanup();
});

describe("JH-043 job details page", () => {
  it("loads and shows the selected job", async () => {
    apiFetch.mockResolvedValue(mockResponse(details()));

    renderDetails();

    expect(await screen.findByRole("heading", { name: "Data Analyst" })).toBeInTheDocument();
    expect(screen.getByText("Direct skill matches include Python.")).toBeInTheDocument();
    expect(apiFetch).toHaveBeenCalledWith(
      "/api/jobs/2",
      expect.objectContaining({ signal: expect.any(AbortSignal) })
    );

    const link = screen.getByRole("link", { name: /View the original posting/ });
    expect(link).toHaveAttribute("href", "https://example.com/jobs/2");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("labels a missing match explanation", async () => {
    apiFetch.mockResolvedValue(mockResponse(details({}, null)));

    renderDetails();

    expect(
      await screen.findByText("No match explanation is available for this job.")
    ).toBeInTheDocument();
  });

  it("does not link a javascript: URL", async () => {
    apiFetch.mockResolvedValue(mockResponse(details({ job_url: "javascript:alert(1)" })));

    renderDetails();

    expect(await screen.findByText("The original posting isn't available.")).toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: /View the original posting/ })
    ).not.toBeInTheDocument();
  });

  it("shows script text in the description as plain text", async () => {
    const description = '<script>window.hacked = true</script><img src=x onerror="alert(1)">';
    apiFetch.mockResolvedValue(mockResponse(details({ description })));

    const { container } = render(<JobDetails jobId={2} onBack={vi.fn()} />);

    expect(await screen.findByText(description)).toBeInTheDocument();
    expect(container.querySelector("script")).toBeNull();
    expect(container.querySelector("img")).toBeNull();
    expect(window.hacked).toBeUndefined();
  });

  it("labels Adzuna descriptions as shortened", async () => {
    apiFetch.mockResolvedValue(mockResponse(details()));

    renderDetails();

    expect(await screen.findByText(/Shortened description from the source/)).toBeInTheDocument();
  });

  it("does not label descriptions from other sources as shortened", async () => {
    apiFetch.mockResolvedValue(mockResponse(details({ source: "manual" })));

    renderDetails();

    expect(await screen.findByText("Analyze data with Python and SQL...")).toBeInTheDocument();
    expect(screen.queryByText(/Shortened description/)).not.toBeInTheDocument();
  });

  it("labels a missing description", async () => {
    apiFetch.mockResolvedValue(mockResponse(details({ description: null })));

    renderDetails();

    expect(await screen.findByText("No description is available for this job.")).toBeInTheDocument();
    expect(screen.queryByText(/Shortened description/)).not.toBeInTheDocument();
  });

  it("shows a not-found message and a way back on a 404", async () => {
    apiFetch.mockResolvedValue(mockResponse({ detail: "Job not found." }, 404));

    const onBack = renderDetails();

    expect(await screen.findByRole("alert")).toHaveTextContent("This job couldn't be found.");
    await userEvent.click(screen.getByRole("button", { name: "Back to dashboard" }));
    expect(onBack).toHaveBeenCalled();
  });

  it("shows an invalid-link message for a bad job id", async () => {
    apiFetch.mockResolvedValue(mockResponse({ detail: [] }, 422));

    renderDetails();

    expect(await screen.findByRole("alert")).toHaveTextContent("This job link isn't valid.");
    expect(screen.getByRole("button", { name: "Back to dashboard" })).toBeInTheDocument();
  });

  it("shows an error message when the request fails", async () => {
    apiFetch.mockRejectedValue(new TypeError("Failed to fetch"));

    renderDetails();

    expect(await screen.findByRole("alert")).toHaveTextContent("We couldn't load this job.");
    expect(screen.getByRole("button", { name: "Back to dashboard" })).toBeInTheDocument();
  });
});
