// @vitest-environment jsdom

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom/vitest";

import App from "./App";

// GenAI attribution:
// Developed with assistance from ChatGPT (OpenAI).
// Prompt: Add regression tests for JH-021 PR review feedback.
// Verify that saved remote-only search preferences restrict displayed
// job postings, local filters cannot bypass saved restrictions,
// preference loading errors do not expose unrestricted results,
// and anonymous browsing continues to work.
//
// Follow-up prompt: Verify unmatched saved preference warnings,
// continued filtering when some preferences match, incompatible
// combinations of individually valid preferences, and independent
// matching against all current postings.
//
// Reviewed and adapted for the CS467 Job Hunting AI project.

const apiFetch = vi.fn();

vi.mock("./api", () => ({
  apiFetch: (...args) => apiFetch(...args),
  setUnauthorizedHandler: vi.fn(),
}));

vi.mock("./components/ProfileForm", () => ({
  default: () => <div>Mock Profile Form</div>,
}));

vi.mock("./components/SearchPreferencesForm", () => ({
  default: () => <div>Mock Search Preferences Form</div>,
}));

function mockResponse(data, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => data,
  };
}

const signedInUser = {
  id: 1,
  email: "test@example.com",
};

const remoteOnlyPreferences = {
  job_titles: [],
  locations: [],
  workplace_type: ["remote"],
  salary_min: null,
  salary_max: null,
  salary_currency: "USD",
  result_count: 20,
};

async function openJobPostings() {
  const user = userEvent.setup();

  await user.click(
    screen.getByText("Job Postings", {
      selector: "button, a, span",
    })
  );

  return user;
}

beforeEach(() => {
  vi.clearAllMocks();

  apiFetch.mockResolvedValue(
    mockResponse(remoteOnlyPreferences)
  );

  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      mockResponse({ user: signedInUser })
    )
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("JH-021 saved search preferences integration", () => {
  it("applies saved remote-only preferences to job postings", async () => {
    render(<App />);

    await screen.findByText("test@example.com");

    await openJobPostings();

    expect(
      await screen.findByText(/Your saved job search preferences are applied/)
    ).toBeInTheDocument();

    const results = screen.getByText("Matching jobs")
      .closest(".postings-panel");

    expect(
      within(results).getByText("Data Analyst")
    ).toBeInTheDocument();

    expect(
      within(results).queryByText("Frontend Developer")
    ).not.toBeInTheDocument();

    expect(
      within(results).queryByText("Product Designer")
    ).not.toBeInTheDocument();

    expect(
      within(results).getByText("1 results")
    ).toBeInTheDocument();

    expect(apiFetch).toHaveBeenCalledWith(
      "/api/preferences",
      expect.objectContaining({
        signal: expect.any(AbortSignal),
      })
    );
  });

  it("does not allow Any type to bypass saved remote-only restrictions", async () => {
    render(<App />);

    await screen.findByText("test@example.com");

    const user = await openJobPostings();

    await screen.findByText(
      /Your saved job search preferences are applied/
    );

    const workplaceFilter = screen.getByLabelText("Workplace type");

    expect(workplaceFilter).toHaveValue("Any type");

    await user.selectOptions(workplaceFilter, "Hybrid");

    expect(
      screen.queryByText("Frontend Developer")
    ).not.toBeInTheDocument();

    expect(
      screen.getByText("0 results")
    ).toBeInTheDocument();

    await user.selectOptions(workplaceFilter, "Any type");

    expect(
      screen.getByText("Data Analyst")
    ).toBeInTheDocument();

    expect(
      screen.queryByText("Frontend Developer")
    ).not.toBeInTheDocument();

    expect(
      screen.queryByText("Product Designer")
    ).not.toBeInTheDocument();
  });

  it("hides job results when saved preferences cannot be loaded", async () => {
    apiFetch.mockResolvedValue(
      mockResponse(
        {
          error: {
            message: "Unable to load preferences",
          },
        },
        500
      )
    );

    render(<App />);

    await screen.findByText("test@example.com");

    await openJobPostings();

    expect(
      await screen.findByRole("alert")
    ).toHaveTextContent(
      "Unable to load preferences"
    );

    expect(
      screen.queryByText("Data Analyst")
    ).not.toBeInTheDocument();

    expect(
      screen.queryByText("Frontend Developer")
    ).not.toBeInTheDocument();

    expect(
      screen.queryByText("Product Designer")
    ).not.toBeInTheDocument();

    expect(
      screen.getByText("0 results")
    ).toBeInTheDocument();
  });

  it("allows anonymous users to browse demonstration postings", async () => {
    fetch.mockResolvedValueOnce(
      mockResponse({}, 401)
    );

    render(<App />);

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        "/api/auth/me",
        expect.objectContaining({
          credentials: "include",
        })
      );
    });

    await openJobPostings();

    expect(
      screen.getByText("Frontend Developer")
    ).toBeInTheDocument();

    expect(
      screen.getByText("Data Analyst")
    ).toBeInTheDocument();

    expect(
      screen.getByText("Product Designer")
    ).toBeInTheDocument();

    expect(apiFetch).not.toHaveBeenCalled();
  });

  // GenAI attribution:
  // Developed with assistance from ChatGPT (OpenAI).
  // Prompt: Test Job Postings warnings for unmatched saved values,
  // incompatible saved preferences, independent validation against
  // the full dataset, and empty results caused by local filters.
  // Reviewed and adapted for the CS467 Job Hunting AI project.

  it("shows unmatched saved values even when other preferences return results", async () => {
    apiFetch.mockResolvedValue(
      mockResponse({
        ...remoteOnlyPreferences,
        job_titles: [
          "Data Analyst",
          "Software Engineer",
        ],
        locations: [
          "Remote",
          "Portland, OR",
        ],
      })
    );

    render(<App />);

    await screen.findByText("test@example.com");

    await openJobPostings();

    expect(
      await screen.findByText(
        /No current postings match your saved job title “Software Engineer”/
      )
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        /No current postings match your saved location “Portland, OR”/
      )
    ).toBeInTheDocument();

    expect(
      screen.getByText("Data Analyst")
    ).toBeInTheDocument();

    expect(
      screen.queryByText("Frontend Developer")
    ).not.toBeInTheDocument();

    expect(
      screen.queryByText("Product Designer")
    ).not.toBeInTheDocument();

    expect(
      screen.getByText("1 results")
    ).toBeInTheDocument();

    expect(
      screen.queryByText(
        /No current postings match all your saved preferences/
      )
    ).not.toBeInTheDocument();
  });

  it("explains when individually valid saved preferences have no combined matches", async () => {
    apiFetch.mockResolvedValue(
      mockResponse({
        ...remoteOnlyPreferences,
        job_titles: ["Frontend Developer"],
        locations: ["New York, NY"],
        workplace_type: [],
      })
    );

    render(<App />);

    await screen.findByText("test@example.com");

    await openJobPostings();

    expect(
      await screen.findByText(
        /No current postings match all your saved preferences/
      )
    ).toBeInTheDocument();

    expect(
      screen.getByText("0 results")
    ).toBeInTheDocument();

    expect(
      screen.queryByText(
        /No current postings match your saved job title/
      )
    ).not.toBeInTheDocument();

    expect(
      screen.queryByText(
        /No current postings match your saved location/
      )
    ).not.toBeInTheDocument();

    expect(
      screen.queryByText("Frontend Developer")
    ).not.toBeInTheDocument();

    expect(
      screen.queryByText("Product Designer")
    ).not.toBeInTheDocument();

    expect(
      screen.queryByText("Data Analyst")
    ).not.toBeInTheDocument();
  });

  it("does not mark a valid city as unmatched because of remote-only restrictions", async () => {
    apiFetch.mockResolvedValue(
      mockResponse({
        ...remoteOnlyPreferences,
        job_titles: ["Frontend Developer"],
        locations: ["San Francisco, CA"],
        workplace_type: ["remote"],
      })
    );

    render(<App />);

    await screen.findByText("test@example.com");

    await openJobPostings();

    expect(
      await screen.findByText(
        /No current postings match all your saved preferences/
      )
    ).toBeInTheDocument();

    expect(
      screen.queryByText(
        /No current postings match your saved location/
      )
    ).not.toBeInTheDocument();

    expect(
      screen.queryByText(
        /No current postings match your saved job title/
      )
    ).not.toBeInTheDocument();

    expect(
      screen.getByText("0 results")
    ).toBeInTheDocument();

    expect(
      screen.queryByText("Frontend Developer")
    ).not.toBeInTheDocument();
  });

  it("distinguishes empty local search results from incompatible saved preferences", async () => {
    render(<App />);

    await screen.findByText("test@example.com");

    const user = await openJobPostings();

    await screen.findByText(
      /Your saved job search preferences are applied/
    );

    expect(
      screen.getByText("Data Analyst")
    ).toBeInTheDocument();

    const searchInput = screen.getByLabelText("Job title");

    await user.type(searchInput, "Frontend Developer");

    expect(
      screen.getByText("0 results")
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        /No matching jobs. Try changing your search or filters/
      )
    ).toBeInTheDocument();

    expect(
      screen.queryByText(
        /No current postings match all your saved preferences/
      )
    ).not.toBeInTheDocument();

    expect(
      screen.queryByText(
        /No current postings match your saved job title/
      )
    ).not.toBeInTheDocument();

    expect(
      screen.queryByText(
        /No current postings match your saved location/
      )
    ).not.toBeInTheDocument();

    await user.clear(searchInput);

    expect(
      screen.getByText("Data Analyst")
    ).toBeInTheDocument();

    expect(
      screen.getByText("1 results")
    ).toBeInTheDocument();

    expect(
      screen.queryByText("Frontend Developer")
    ).not.toBeInTheDocument();
  });
});