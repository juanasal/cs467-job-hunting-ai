// @vitest-environment jsdom

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom/vitest";

import RecommendedJobs from "./RecommendedJobs";

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

const recentTime = new Date().toISOString();

function recommendation(jobId, title, score, jobOverrides = {}) {
  return {
    job: {
      job_id: jobId,
      source: "adzuna",
      title,
      company: "Example Corp",
      location: "Portland, OR",
      workplace_type: "hybrid",
      salary_min: null,
      salary_max: null,
      date_posted: "2026-10-18",
      job_url: "https://example.com/jobs/1",
      retrieved_at: recentTime,
      ...jobOverrides,
    },
    match: { user_id: 1, job_id: jobId, match_score: score },
  };
}

function renderDashboard(props = {}) {
  return render(
    <RecommendedJobs signedIn authLoading={false} onGoToProfile={vi.fn()} {...props} />
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  cleanup();
});

describe("JH-042 ranked job dashboard", () => {
  it("shows jobs in the order the API returns them", async () => {
    // A lower score is returned first to prove the UI does not re-sort.
    apiFetch.mockResolvedValue(
      mockResponse({
        recommendations: [
          recommendation(3, "Backend Engineer", 60),
          recommendation(1, "Frontend Developer", 90),
          recommendation(2, "Data Analyst", 75),
        ],
      })
    );

    renderDashboard();

    const titles = await screen.findAllByRole("heading", { level: 3 });
    expect(titles.map((title) => title.textContent)).toEqual([
      "Backend Engineer",
      "Frontend Developer",
      "Data Analyst",
    ]);

    expect(screen.getByText("Fit score: 60 / 100")).toBeInTheDocument();
    expect(screen.getAllByText("Source: Adzuna")).toHaveLength(3);
    expect(screen.getAllByText("Posted Oct 18, 2026")).toHaveLength(3);
    expect(screen.getByRole("link", { name: "The Adzuna API" })).toBeInTheDocument();
    expect(screen.queryByText(/may be outdated/)).not.toBeInTheDocument();
    expect(apiFetch).toHaveBeenCalledWith(
      "/api/recommendations",
      expect.objectContaining({ signal: expect.any(AbortSignal) })
    );
  });

  it("points to the profile page when there are no recommendations", async () => {
    apiFetch.mockResolvedValue(mockResponse({ recommendations: [] }));
    const onGoToProfile = vi.fn();

    renderDashboard({ onGoToProfile });

    expect(await screen.findByText(/No recommended jobs yet/)).toBeInTheDocument();

    await userEvent.click(
      screen.getByRole("button", { name: "Go to profile & preferences" })
    );
    expect(onGoToProfile).toHaveBeenCalled();
  });

  it("shows an error message when the request fails", async () => {
    apiFetch.mockResolvedValue(
      mockResponse({ error: { message: "Server error" } }, 500)
    );

    renderDashboard();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "We couldn't load your recommended jobs."
    );
    expect(screen.queryByRole("heading", { level: 3 })).not.toBeInTheDocument();
  });

  it("shows an error message when the server cannot be reached", async () => {
    apiFetch.mockRejectedValue(new TypeError("Failed to fetch"));

    renderDashboard();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "We couldn't load your recommended jobs."
    );
  });

  it("labels missing fields instead of leaving them blank", async () => {
    apiFetch.mockResolvedValue(
      mockResponse({
        recommendations: [
          {
            ...recommendation(5, "QA Engineer", 50, {
              company: null,
              location: null,
              source: null,
              date_posted: null,
            }),
            match: null,
          },
        ],
      })
    );

    renderDashboard();

    const card = (await screen.findByText("QA Engineer")).closest("article");
    expect(within(card).getByText("Company not listed")).toBeInTheDocument();
    expect(within(card).getByText("Location not listed")).toBeInTheDocument();
    expect(within(card).getByText("Source not listed")).toBeInTheDocument();
    expect(within(card).getByText("Posting date not listed")).toBeInTheDocument();
    expect(within(card).getByText("Fit score not available")).toBeInTheDocument();
    expect(card).not.toHaveTextContent(/undefined|null/);
  });

  it("warns when the newest result was retrieved more than 7 days ago", async () => {
    apiFetch.mockResolvedValue(
      mockResponse({
        recommendations: [
          recommendation(1, "Frontend Developer", 90, {
            retrieved_at: "2020-01-01T00:00:00Z",
          }),
        ],
      })
    );

    renderDashboard();

    expect(await screen.findByText(/These results may be outdated/)).toBeInTheDocument();
  });

  it("asks signed-out users to sign in without calling the API", () => {
    renderDashboard({ signedIn: false });

    expect(screen.getByText(/Sign in to see job recommendations/)).toBeInTheDocument();
    expect(apiFetch).not.toHaveBeenCalled();
  });

  it("opens the details of the job that was clicked (JH-043)", async () => {
    apiFetch.mockResolvedValue(
      mockResponse({
        recommendations: [
          recommendation(1, "Frontend Developer", 90),
          recommendation(2, "Data Analyst", 75),
        ],
      })
    );
    const onViewJob = vi.fn();

    renderDashboard({ onViewJob });

    await userEvent.click(
      await screen.findByRole("button", { name: "View details for Data Analyst" })
    );

    expect(onViewJob).toHaveBeenCalledWith(2);
  });
});
