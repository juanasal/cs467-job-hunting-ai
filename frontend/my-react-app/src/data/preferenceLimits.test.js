/*
GenAI attribution:
Developed with assistance from ChatGPT (OpenAI).
Prompt: Write unit tests for JH-022 salary and result-count
validation, including optional salary bounds, invalid ranges,
decimal precision, numeric limits, and API serialization.
Reviewed and adapted for the CS467 Job Hunting AI project.
*/

import { describe, expect, it } from "vitest";

import {
  MAX_SALARY,
  MAX_RESULT_COUNT,
  validatePreferenceLimits,
  serializeSalary,
} from "./preferenceLimits";

const validPreferences = {
  salary_min: "80000.00",
  salary_max: "150000.00",
  result_count: 20,
};

describe("JH-022 preference limits", () => {
  it("accepts a valid salary range and result count", () => {
    expect(
      validatePreferenceLimits(validPreferences)
    ).toBe("");
  });

  it("accepts empty salary bounds", () => {
    expect(
      validatePreferenceLimits({
        ...validPreferences,
        salary_min: "",
        salary_max: null,
      })
    ).toBe("");
  });

  it.each([
    ["80000", null],
    [null, "150000"],
    ["80000", "80000"],
    ["0", "0"],
    ["80000.25", "150000.99"],
  ])(
    "accepts valid salary bounds %s and %s",
    (minimum, maximum) => {
      expect(
        validatePreferenceLimits({
          ...validPreferences,
          salary_min: minimum,
          salary_max: maximum,
        })
      ).toBe("");
    }
  );

  it("rejects a minimum salary greater than maximum salary", () => {
    expect(
      validatePreferenceLimits({
        ...validPreferences,
        salary_min: "150000",
        salary_max: "80000",
      })
    ).toBe(
      "Minimum salary cannot exceed maximum salary."
    );
  });

  it.each([
    "-1",
    "abc",
    "NaN",
    "Infinity",
    "80000.123",
    "10000000000",
    "1e5",
  ])("rejects invalid minimum salary %s", (value) => {
    expect(
      validatePreferenceLimits({
        ...validPreferences,
        salary_min: value,
      })
    ).toContain("Minimum salary");
  });

  it.each([
    "-1",
    "abc",
    "150000.123",
    "10000000000",
  ])("rejects invalid maximum salary %s", (value) => {
    expect(
      validatePreferenceLimits({
        ...validPreferences,
        salary_max: value,
      })
    ).toContain("Maximum salary");
  });

  it("accepts the maximum supported salary", () => {
    expect(
      validatePreferenceLimits({
        ...validPreferences,
        salary_min: MAX_SALARY,
        salary_max: MAX_SALARY,
      })
    ).toBe("");
  });

  it.each([
    1,
    20,
    100,
    MAX_RESULT_COUNT,
    "35",
  ])("accepts valid result count %s", (count) => {
    expect(
      validatePreferenceLimits({
        ...validPreferences,
        result_count: count,
      })
    ).toBe("");
  });

  it.each([
    0,
    -1,
    1.5,
    "",
    null,
    "abc",
    "Infinity",
    "1e2",
    MAX_RESULT_COUNT + 1,
  ])("rejects invalid result count %s", (count) => {
    expect(
      validatePreferenceLimits({
        ...validPreferences,
        result_count: count,
      })
    ).toContain(
      "Maximum number of recommendations"
    );
  });

  it("serializes empty salary values as null", () => {
    expect(serializeSalary("")).toBeNull();
    expect(serializeSalary(null)).toBeNull();
    expect(serializeSalary(undefined)).toBeNull();
  });

  it("preserves salary precision during serialization", () => {
    expect(serializeSalary("80000.00")).toBe("80000.00");
    expect(serializeSalary("80000.25")).toBe("80000.25");
    expect(serializeSalary(80000)).toBe("80000");
    expect(serializeSalary(0)).toBe("0");
  });
});