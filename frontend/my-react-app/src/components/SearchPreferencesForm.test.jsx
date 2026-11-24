/*
GenAI attribution:
Developed with assistance from ChatGPT (OpenAI).
Prompt: Write Vitest and React Testing Library tests for JH-021
search preference controls, covering GET/PUT, validation,
remote-only restrictions, unrelated preference preservation,
and API errors.

Follow-up prompt: Add a regression test for FastAPI HTTP 422
responses to verify that field-level validation details are
displayed instead of the generic "Request validation failed"
message.

Reviewed and adapted for the CS467 Job Hunting AI project.
*/

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom/vitest";

vi.mock("../api", () => ({
  apiFetch: vi.fn(),
}));

import { apiFetch } from "../api";
import SearchPreferencesForm from "./SearchPreferencesForm";

const savedPreferences = {
  user_id: 1,
  job_titles: ["Software Engineer"],
  locations: ["Portland, OR"],
  workplace_type: ["hybrid"],
  salary_min: "80000.00",
  salary_max: "150000.00",
  salary_currency: "USD",
  result_count: 35,
};

function mockResponse(data, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: vi.fn().mockResolvedValue(data),
  };
}

function mockApi(initial = savedPreferences) {
  apiFetch.mockImplementation(async (path, options = {}) => {
    if (path !== "/api/preferences") {
      throw new Error(`Unexpected API path: ${path}`);
    }

    if (options.method === "PUT") {
      return mockResponse({
        ...initial,
        ...JSON.parse(options.body),
      });
    }

    return mockResponse(initial);
  });
}

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  cleanup();
});

describe("SearchPreferencesForm (JH-021)", () => {
  it("loads saved titles, locations, and workplace preferences", async () => {
    mockApi();
    render(<SearchPreferencesForm />);

    expect(await screen.findByText("Software Engineer")).toBeInTheDocument();
    expect(screen.getByText("Portland, OR")).toBeInTheDocument();
    expect(screen.getByLabelText("Hybrid")).toBeChecked();
    expect(screen.getByLabelText("Remote")).not.toBeChecked();
    expect(screen.getByLabelText("On-site")).not.toBeChecked();
  });

  it("saves updated preferences without resetting salary or result count", async () => {
    mockApi();
    const user = userEvent.setup();
    render(<SearchPreferencesForm />);

    await screen.findByText("Software Engineer");

    await user.type(
      screen.getByLabelText("Preferred Job Titles"),
      "Security Engineer"
    );

    const titleField = screen.getByLabelText("Preferred Job Titles");
    const titleContainer = titleField.closest(".profile-form-field");

    await user.click(
      within(titleContainer).getByRole("button", { name: "Add" })
    );

    await user.click(screen.getByLabelText("Remote"));
    await user.click(screen.getByRole("button", { name: "Save Preferences" }));

    expect(
      await screen.findByText(
        "Your search preferences have been saved successfully."
      )
    ).toBeInTheDocument();

    const putCall = apiFetch.mock.calls.find(
      ([path, options]) =>
        path === "/api/preferences" && options?.method === "PUT"
    );

    expect(putCall).toBeDefined();

    const payload = JSON.parse(putCall[1].body);

    expect(payload.job_titles).toEqual([
      "Software Engineer",
      "Security Engineer",
    ]);
    expect(payload.locations).toEqual(["Portland, OR"]);
    expect(payload.workplace_type).toEqual(["hybrid", "remote"]);
    expect(payload.salary_min).toBe("80000.00");
    expect(payload.salary_max).toBe("150000.00");
    expect(payload.salary_currency).toBe("USD");
    expect(payload.result_count).toBe(35);
  });

  it("rejects duplicate job titles", async () => {
    mockApi();
    const user = userEvent.setup();
    render(<SearchPreferencesForm />);

    await screen.findByText("Software Engineer");

    await user.type(
      screen.getByLabelText("Preferred Job Titles"),
      "software engineer"
    );

    const field = screen
      .getByLabelText("Preferred Job Titles")
      .closest(".profile-form-field");

    await user.click(
      within(field).getByRole("button", { name: "Add" })
    );

    expect(screen.getByRole("alert")).toHaveTextContent(
      "already been added"
    );
  });

  it("rejects empty locations", async () => {
    mockApi();
    const user = userEvent.setup();
    render(<SearchPreferencesForm />);

    await screen.findByText("Software Engineer");

    const field = screen
      .getByLabelText("Preferred Locations")
      .closest(".profile-form-field");

    await user.click(
      within(field).getByRole("button", { name: "Add" })
    );

    expect(screen.getByRole("alert")).toHaveTextContent(
      "must contain 1 to 255 characters"
    );
  });

  it("does not save unfinished text entries", async () => {
    mockApi();
    const user = userEvent.setup();
    render(<SearchPreferencesForm />);

    await screen.findByText("Software Engineer");

    await user.type(
      screen.getByLabelText("Preferred Locations"),
      "Austin, TX"
    );

    await user.click(
      screen.getByRole("button", { name: "Save Preferences" })
    );

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Please add your entered job title or location"
    );

    expect(
      apiFetch.mock.calls.some(
        ([, options]) => options?.method === "PUT"
      )
    ).toBe(false);
  });

  it("preserves a strict remote-only selection", async () => {
    mockApi();
    const user = userEvent.setup();
    render(<SearchPreferencesForm />);

    await screen.findByText("Software Engineer");

    await user.click(screen.getByLabelText("Hybrid"));
    await user.click(screen.getByLabelText("Remote"));

    await user.click(
      screen.getByRole("button", { name: "Save Preferences" })
    );

    expect(
      await screen.findByText(
        "Your search preferences have been saved successfully."
      )
    ).toBeInTheDocument();

    const putCall = apiFetch.mock.calls.find(
      ([, options]) => options?.method === "PUT"
    );

    expect(
      JSON.parse(putCall[1].body).workplace_type
    ).toEqual(["remote"]);
  });

  it("shows an error for unsupported workplace values", async () => {
    mockApi({
      ...savedPreferences,
      workplace_type: ["unknown"],
    });

    render(<SearchPreferencesForm />);

    expect(
      await screen.findByRole("alert")
    ).toHaveTextContent(
      "Unsupported workplace preference"
    );
  });

  it("shows an API error when saving fails", async () => {
    apiFetch.mockImplementation(async (_path, options = {}) => {
      if (options.method === "PUT") {
        return mockResponse(
          { detail: "Unable to save preferences." },
          500
        );
      }

      return mockResponse(savedPreferences);
    });

    const user = userEvent.setup();
    render(<SearchPreferencesForm />);

    await screen.findByText("Software Engineer");

    await user.click(
      screen.getByRole("button", { name: "Save Preferences" })
    );

    expect(
      await screen.findByRole("alert")
    ).toHaveTextContent(
      "Unable to save preferences."
    );
  });

  // JH-021 PR review fix: verify field-level FastAPI validation errors.
  // Developed with assistance from ChatGPT (OpenAI).
  it("shows field-level details for a 422 validation error", async () => {
    apiFetch.mockImplementation(async (_path, options = {}) => {
      if (options.method === "PUT") {
        return mockResponse(
          {
            error: {
              message: "Request validation failed",
              details: [
                {
                  loc: ["body", "job_titles", 0],
                  message: "String should have at least 1 character",
                  type: "string_too_short",
                },
              ],
            },
          },
          422
        );
      }

      return mockResponse(savedPreferences);
    });

    const user = userEvent.setup();
    render(<SearchPreferencesForm />);

    await screen.findByText("Software Engineer");

    await user.click(
      screen.getByRole("button", { name: "Save Preferences" })
    );

    expect(
      await screen.findByRole("alert")
    ).toHaveTextContent(
      "job_titles.0: String should have at least 1 character"
    );

    expect(
      screen.getByRole("alert")
    ).not.toHaveTextContent(
      "Request validation failed"
    );
  });
});
