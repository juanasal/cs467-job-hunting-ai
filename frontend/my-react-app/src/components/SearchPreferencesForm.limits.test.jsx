// @vitest-environment jsdom

/*
GenAI attribution:
Developed with assistance from ChatGPT (OpenAI).
Prompt: Write React Testing Library integration tests for
JH-022 salary range and maximum recommendation controls.
Verify loading, saving, reloading, optional salary bounds,
invalid values, API payload types, explanatory text,
and preservation of existing search preferences.
Reviewed and adapted for the CS467 Job Hunting AI project.
*/

import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";

import {
  cleanup,
  render,
  screen,
} from "@testing-library/react";

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
  strict_location: true,
  strict_workplace: false,
  strict_salary: true,
};

function mockResponse(data, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: vi.fn().mockResolvedValue(data),
  };
}

function mockApi(initial = savedPreferences) {
  let stored = { ...initial };

  apiFetch.mockImplementation(
    async (path, options = {}) => {
      if (path !== "/api/preferences") {
        throw new Error(`Unexpected API path: ${path}`);
      }

      if (options.method === "PUT") {
        stored = {
          ...stored,
          ...JSON.parse(options.body),
        };
      }

      return mockResponse(stored);
    }
  );
}

async function renderForm() {
  const user = userEvent.setup();

  render(<SearchPreferencesForm />);

  const minimum = await screen.findByLabelText(
    "Minimum salary (USD/year)"
  );

  const maximum = screen.getByLabelText(
    "Maximum salary (USD/year)"
  );

  const count = screen.getByLabelText(
    "Maximum number of recommendations"
  );

  const save = screen.getByRole("button", {
    name: "Save Preferences",
  });

  return {
    user,
    minimum,
    maximum,
    count,
    save,
  };
}

async function replaceValue(user, input, value) {
  await user.clear(input);

  if (value !== "") {
    await user.type(input, String(value));
  }
}

function getPutPayload() {
  const call = apiFetch.mock.calls.find(
    ([path, options]) =>
      path === "/api/preferences" &&
      options?.method === "PUT"
  );

  return call ? JSON.parse(call[1].body) : null;
}

async function expectSaved() {
  expect(
    await screen.findByText(
      "Your search preferences have been saved successfully."
    )
  ).toBeInTheDocument();
}

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  cleanup();
});

describe("SearchPreferencesForm (JH-022)", () => {
  it("loads saved salary bounds and recommendation count", async () => {
    mockApi();

    const { minimum, maximum, count } =
      await renderForm();

    expect(minimum).toHaveValue(80000);
    expect(maximum).toHaveValue(150000);
    expect(count).toHaveValue(35);
  });

  it("shows empty salary fields and the default result count", async () => {
    mockApi({
      ...savedPreferences,
      salary_min: null,
      salary_max: null,
      result_count: 20,
    });

    const { minimum, maximum, count } =
      await renderForm();

    expect(minimum).toHaveValue(null);
    expect(maximum).toHaveValue(null);
    expect(count).toHaveValue(20);
  });

  it("saves updated salary bounds and an integer result count", async () => {
    mockApi();

    const {
      user,
      minimum,
      maximum,
      count,
      save,
    } = await renderForm();

    await replaceValue(user, minimum, "90000.25");
    await replaceValue(user, maximum, "180000");
    await replaceValue(user, count, "50");

    await user.click(save);
    await expectSaved();

    expect(getPutPayload()).toMatchObject({
      salary_min: "90000.25",
      salary_max: "180000",
      salary_currency: "USD",
      result_count: 50,
    });
  });

  it("reloads the updated values after remounting the form", async () => {
    mockApi();

    const {
      user,
      minimum,
      maximum,
      count,
      save,
    } = await renderForm();

    await replaceValue(user, minimum, "95000");
    await replaceValue(user, maximum, "175000");
    await replaceValue(user, count, "40");

    await user.click(save);
    await expectSaved();

    cleanup();

    const reloaded = await renderForm();

    expect(reloaded.minimum).toHaveValue(95000);
    expect(reloaded.maximum).toHaveValue(175000);
    expect(reloaded.count).toHaveValue(40);
  });

  it("saves cleared salary fields as null", async () => {
    mockApi();

    const {
      user,
      minimum,
      maximum,
      save,
    } = await renderForm();

    await user.clear(minimum);
    await user.clear(maximum);

    await user.click(save);
    await expectSaved();

    expect(getPutPayload()).toMatchObject({
      salary_min: null,
      salary_max: null,
    });
  });

  it("allows a salary range with only one bound", async () => {
    mockApi();

    const {
      user,
      minimum,
      maximum,
      save,
    } = await renderForm();

    await replaceValue(user, minimum, "100000");
    await user.clear(maximum);

    await user.click(save);
    await expectSaved();

    expect(getPutPayload()).toMatchObject({
      salary_min: "100000",
      salary_max: null,
    });
  });

  it("rejects a minimum salary greater than maximum salary", async () => {
    mockApi();

    const {
      user,
      minimum,
      maximum,
      save,
    } = await renderForm();

    await replaceValue(user, minimum, "200000");
    await replaceValue(user, maximum, "100000");

    await user.click(save);

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Minimum salary cannot exceed maximum salary."
    );

    expect(getPutPayload()).toBeNull();
  });

  it.each([
    "-1",
    "80000.123",
    "10000000000",
  ])("rejects invalid minimum salary %s", async (value) => {
    mockApi();

    const {
      user,
      minimum,
      save,
    } = await renderForm();

    await replaceValue(user, minimum, value);
    await user.click(save);

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Minimum salary"
    );

    expect(getPutPayload()).toBeNull();
  });

  it.each([
    "0",
    "-1",
    "1.5",
    "",
    "4294967296",
  ])("rejects invalid result count %s", async (value) => {
    mockApi();

    const {
      user,
      count,
      save,
    } = await renderForm();

    await replaceValue(user, count, value);
    await user.click(save);

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Maximum number of recommendations"
    );

    expect(getPutPayload()).toBeNull();
  });

  it("accepts a result count of one", async () => {
    mockApi();

    const {
      user,
      count,
      save,
    } = await renderForm();

    await replaceValue(user, count, "1");

    await user.click(save);
    await expectSaved();

    expect(getPutPayload().result_count).toBe(1);
  });

  it("explains missing salary information", async () => {
    mockApi();

    await renderForm();

    expect(
      screen.getByText(
        /Jobs without salary information may still appear/
      )
    ).toBeInTheDocument();
  });

  it("explains that fewer recommendations may be available", async () => {
    mockApi();

    await renderForm();

    expect(
      screen.getByText(
        /Fewer results may be available/
      )
    ).toBeInTheDocument();
  });

  it("explains strict salary behavior", async () => {
    mockApi();

    await renderForm();

    expect(
      screen.getByText(
        /Jobs with a confirmed salary mismatch are excluded/
      )
    ).toBeInTheDocument();
  });

  it("explains non-strict salary behavior", async () => {
    mockApi({
      ...savedPreferences,
      strict_salary: false,
    });

    await renderForm();

    expect(
      screen.getByText(
        /Jobs outside your preferred salary range may still be recommended/
      )
    ).toBeInTheDocument();
  });

  it("preserves existing preferences when updating salary and count", async () => {
    mockApi();

    const {
      user,
      minimum,
      count,
      save,
    } = await renderForm();

    await replaceValue(user, minimum, "85000");
    await replaceValue(user, count, "25");

    await user.click(save);
    await expectSaved();

    expect(getPutPayload()).toMatchObject({
      job_titles: ["Software Engineer"],
      locations: ["Portland, OR"],
      workplace_type: ["hybrid"],
      salary_min: "85000",
      salary_max: "150000.00",
      salary_currency: "USD",
      result_count: 25,
      strict_location: true,
      strict_workplace: false,
      strict_salary: true,
    });
  });
});