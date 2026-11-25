/*
GenAI attribution:
Developed with assistance from ChatGPT (OpenAI).
Prompt: Create JH-020 React Testing Library tests for
incomplete profile guidance, education and experience
validation, saving profile data through the existing API,
and reloading persisted profile values.
Reviewed and adapted for the CS467 Job Hunting AI project.
*/

import "@testing-library/jest-dom/vitest";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ProfileForm from "./ProfileForm";
import { apiFetch } from "../api";

vi.mock("../api", () => ({
  apiFetch: vi.fn(),
}));

const savedProfile = {
  user_id: 1,
  skills: ["Python"],
  education_level: "bachelor",
  experience_level: "mid",
};

function mockResponse(status, data) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: vi.fn().mockResolvedValue(data),
  };
}

async function loadEmptyProfile() {
  apiFetch.mockResolvedValue(mockResponse(404, {}));

  render(<ProfileForm />);

  await screen.findByText("Complete your profile");
}

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  cleanup();
});

describe("JH-020 profile completion", () => {
  it("shows specific guidance for all missing fields", async () => {
    await loadEmptyProfile();

    expect(
      screen.getByText("Add at least one skill.")
    ).toBeInTheDocument();

    expect(
      screen.getByText("Select your education level.")
    ).toBeInTheDocument();

    expect(
      screen.getByText("Select your experience level.")
    ).toBeInTheDocument();
  });

  it("updates missing-field guidance as the user fills the form", async () => {
    const user = userEvent.setup();

    await loadEmptyProfile();

    await user.type(
      screen.getByPlaceholderText("e.g. Python, SQL, React"),
      "Python"
    );

    await user.click(screen.getByRole("button", { name: "Add" }));

    expect(
      screen.queryByText("Add at least one skill.")
    ).not.toBeInTheDocument();

    await user.selectOptions(
      screen.getByLabelText("Education Level"),
      "bachelor"
    );

    expect(
      screen.queryByText("Select your education level.")
    ).not.toBeInTheDocument();

    await user.selectOptions(
      screen.getByLabelText("Experience Level"),
      "mid"
    );

    expect(
      screen.getByText(
        "All required fields are filled. Save your changes."
      )
    ).toBeInTheDocument();
  });

  it("prevents saving an incomplete profile", async () => {
    const user = userEvent.setup();

    await loadEmptyProfile();

    await user.click(
      screen.getByRole("button", { name: "Save Changes" })
    );

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Please complete the following:"
    );

    expect(apiFetch).toHaveBeenCalledTimes(1);
    expect(apiFetch).not.toHaveBeenCalledWith(
      "/api/profile",
      expect.objectContaining({ method: "PUT" })
    );
  });

  it("saves skills, education, and experience together", async () => {
    const user = userEvent.setup();

    apiFetch
      .mockResolvedValueOnce(mockResponse(404, {}))
      .mockResolvedValueOnce(mockResponse(200, savedProfile));

    render(<ProfileForm />);

    await screen.findByText("Complete your profile");

    await user.type(
      screen.getByPlaceholderText("e.g. Python, SQL, React"),
      "Python"
    );

    await user.click(screen.getByRole("button", { name: "Add" }));

    await user.selectOptions(
      screen.getByLabelText("Education Level"),
      "bachelor"
    );

    await user.selectOptions(
      screen.getByLabelText("Experience Level"),
      "mid"
    );

    await user.click(
      screen.getByRole("button", { name: "Save Changes" })
    );

    await waitFor(() => {
      expect(apiFetch).toHaveBeenCalledWith(
        "/api/profile",
        expect.objectContaining({
          method: "PUT",
          body: JSON.stringify({
            skills: ["Python"],
            education_level: "bachelor",
            experience_level: "mid",
          }),
        })
      );
    });

    expect(
      await screen.findByText(
        "Your profile has been saved successfully."
      )
    ).toBeInTheDocument();

    expect(
      screen.getByText("Your profile is complete and saved.")
    ).toBeInTheDocument();
  });

  it("restores saved education and experience when the form reloads", async () => {
    apiFetch.mockResolvedValue(mockResponse(200, savedProfile));

    const { unmount } = render(<ProfileForm />);

    expect(
      await screen.findByText("Your profile is complete and saved.")
    ).toBeInTheDocument();

    expect(screen.getByLabelText("Education Level")).toHaveValue(
      "bachelor"
    );

    expect(screen.getByLabelText("Experience Level")).toHaveValue(
      "mid"
    );

    expect(screen.getByText("Python")).toBeInTheDocument();

    unmount();

    render(<ProfileForm />);

    expect(
      await screen.findByText("Your profile is complete and saved.")
    ).toBeInTheDocument();

    expect(screen.getByLabelText("Education Level")).toHaveValue(
      "bachelor"
    );

    expect(screen.getByLabelText("Experience Level")).toHaveValue(
      "mid"
    );

    expect(apiFetch).toHaveBeenCalledTimes(2);
  });

  it("marks the profile as unsaved after editing", async () => {
    const user = userEvent.setup();

    apiFetch.mockResolvedValue(mockResponse(200, savedProfile));

    render(<ProfileForm />);

    await screen.findByText("Your profile is complete and saved.");

    await user.selectOptions(
      screen.getByLabelText("Education Level"),
      "master"
    );

    expect(
      screen.getByText(
        "All required fields are filled. Save your changes."
      )
    ).toBeInTheDocument();

    expect(
      screen.queryByText("Your profile is complete and saved.")
    ).not.toBeInTheDocument();
  });

  it("shows a specific error when the API rejects a save", async () => {
    const user = userEvent.setup();

    apiFetch
      .mockResolvedValueOnce(mockResponse(200, savedProfile))
      .mockResolvedValueOnce(
        mockResponse(422, {
          detail: "Invalid profile information.",
        })
      );

    render(<ProfileForm />);

    await screen.findByText("Your profile is complete and saved.");

    await user.click(
      screen.getByRole("button", { name: "Save Changes" })
    );

    expect(
      await screen.findByRole("alert")
    ).toHaveTextContent("Invalid profile information.");
  });
});
