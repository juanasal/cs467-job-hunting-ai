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
});
