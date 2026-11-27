/*
GenAI attribution:
Developed with assistance from ChatGPT (OpenAI).
Prompt: Write regression tests for JH-021 PR review feedback.
Verify case-insensitive substring matching, unmatched saved
titles and locations, independent validation against the full
postings dataset, strict workplace restrictions, and incompatible
combinations of individually valid preferences.

Reviewed and adapted for the CS467 Job Hunting AI project.
*/

import { describe, expect, it } from "vitest";

import { jobPostings } from "./jobPostings";

import {
  matchesJobTitle,
  matchesJobLocation,
  matchesSavedPreferences,
  getPreferenceWarnings,
} from "./preferenceMatching";

const defaultPreferences = {
  job_titles: [],
  locations: [],
  workplace_type: [],
};

describe("JH-021 preference matching", () => {
  it("matches job titles using case-insensitive substring matching", () => {
    const job = jobPostings[0];

    expect(matchesJobTitle(job, "frontend")).toBe(true);
    expect(matchesJobTitle(job, "DEVELOPER")).toBe(true);
    expect(matchesJobTitle(job, " Frontend ")).toBe(true);
    expect(matchesJobTitle(job, "Software Engineer")).toBe(false);
  });

  it("matches locations using case-insensitive substring matching", () => {
    const job = jobPostings[0];

    expect(matchesJobLocation(job, "san francisco")).toBe(true);
    expect(matchesJobLocation(job, "CA")).toBe(true);
    expect(matchesJobLocation(job, "Portland, OR")).toBe(false);
  });

  it("identifies only job titles without current matches", () => {
    const preferences = {
      ...defaultPreferences,
      job_titles: [
        "Data Analyst",
        "Software Engineer",
        "FRONTEND",
      ],
    };

    const warnings = getPreferenceWarnings(
      jobPostings,
      preferences
    );

    expect(warnings.unmatchedTitles).toEqual([
      "Software Engineer",
    ]);

    expect(warnings.unmatchedLocations).toEqual([]);
    expect(warnings.noCombinedMatches).toBe(false);
  });

  it("identifies only locations without current matches", () => {
    const preferences = {
      ...defaultPreferences,
      locations: [
        "New York",
        "Portland, OR",
        "San Francisco",
      ],
    };

    const warnings = getPreferenceWarnings(
      jobPostings,
      preferences
    );

    expect(warnings.unmatchedLocations).toEqual([
      "Portland, OR",
    ]);

    expect(warnings.unmatchedTitles).toEqual([]);
    expect(warnings.noCombinedMatches).toBe(false);
  });

  it("checks locations against all postings before workplace filtering", () => {
    const preferences = {
      ...defaultPreferences,
      locations: ["San Francisco, CA"],
      workplace_type: ["remote"],
    };

    const warnings = getPreferenceWarnings(
      jobPostings,
      preferences
    );

    expect(warnings.unmatchedLocations).toEqual([]);
    expect(warnings.noCombinedMatches).toBe(true);
  });

  it("checks job titles independently of saved location filters", () => {
    const preferences = {
      ...defaultPreferences,
      job_titles: ["Frontend Developer"],
      locations: ["New York, NY"],
    };

    const warnings = getPreferenceWarnings(
      jobPostings,
      preferences
    );

    expect(warnings.unmatchedTitles).toEqual([]);
    expect(warnings.unmatchedLocations).toEqual([]);
    expect(warnings.noCombinedMatches).toBe(true);
  });

  it("keeps valid saved preferences in effect when other values have no matches", () => {
    const preferences = {
      ...defaultPreferences,
      job_titles: [
        "Data Analyst",
        "Software Engineer",
      ],
      locations: [
        "Remote",
        "Portland, OR",
      ],
      workplace_type: ["remote"],
    };

    const results = jobPostings.filter((job) =>
      matchesSavedPreferences(job, preferences)
    );

    expect(results.map((job) => job.job_id)).toEqual([
      "job-002",
    ]);

    const warnings = getPreferenceWarnings(
      jobPostings,
      preferences
    );

    expect(warnings.unmatchedTitles).toEqual([
      "Software Engineer",
    ]);

    expect(warnings.unmatchedLocations).toEqual([
      "Portland, OR",
    ]);

    expect(warnings.noCombinedMatches).toBe(false);
  });

  it("does not expand strict remote-only restrictions", () => {
    const preferences = {
      ...defaultPreferences,
      workplace_type: ["remote"],
    };

    const results = jobPostings.filter((job) =>
      matchesSavedPreferences(job, preferences)
    );

    expect(results.map((job) => job.job_id)).toEqual([
      "job-002",
    ]);
  });

  it("returns no results when every saved job title is unmatched", () => {
    const preferences = {
      ...defaultPreferences,
      job_titles: ["Unknown Job Title"],
    };

    const results = jobPostings.filter((job) =>
      matchesSavedPreferences(job, preferences)
    );

    const warnings = getPreferenceWarnings(
      jobPostings,
      preferences
    );

    expect(results).toEqual([]);

    expect(warnings.unmatchedTitles).toEqual([
      "Unknown Job Title",
    ]);

    expect(warnings.noCombinedMatches).toBe(true);
  });

  it("does not restrict results when saved preferences are empty", () => {
    const results = jobPostings.filter((job) =>
      matchesSavedPreferences(job, defaultPreferences)
    );

    expect(results).toEqual(jobPostings);

    expect(
      getPreferenceWarnings(jobPostings, defaultPreferences)
    ).toEqual({
      unmatchedTitles: [],
      unmatchedLocations: [],
      noCombinedMatches: false,
    });
  });

  it("handles users without saved preferences", () => {
    const results = jobPostings.filter((job) =>
      matchesSavedPreferences(job, null)
    );

    expect(results).toEqual(jobPostings);

    expect(
      getPreferenceWarnings(jobPostings, null)
    ).toEqual({
      unmatchedTitles: [],
      unmatchedLocations: [],
      noCombinedMatches: false,
    });
  });
});