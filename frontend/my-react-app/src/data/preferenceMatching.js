/*
GenAI attribution:
Developed with assistance from ChatGPT (OpenAI).
Prompt: Address JH-021 PR review feedback by implementing
shared search preference matching and identifying job titles
and locations that have no matching available job postings.
Preserve existing filtering behavior and allow users to save
preferences even when no matching jobs are currently available.
Reviewed and adapted for the CS467 Job Hunting AI project.
*/

function normalize(value) {
  return String(value ?? "").trim().toLowerCase();
}

export function matchesJobTitle(job, title) {
  return normalize(job.title).includes(normalize(title));
}

export function matchesJobLocation(job, location) {
  return normalize(job.location).includes(normalize(location));
}

export function matchesSavedPreferences(job, preferences) {
  const titles = preferences?.job_titles ?? [];
  const locations = preferences?.locations ?? [];
  const workplaceTypes = preferences?.workplace_type ?? [];

  const matchesTitles =
    titles.length === 0 ||
    titles.some((title) => matchesJobTitle(job, title));

  const matchesLocations =
    locations.length === 0 ||
    locations.some((location) =>
      matchesJobLocation(job, location)
    );

  const matchesWorkplace =
    workplaceTypes.length === 0 ||
    workplaceTypes.includes(normalize(job.workplace_type));

  return (
    matchesTitles &&
    matchesLocations &&
    matchesWorkplace
  );
}

export function getPreferenceWarnings(jobs, preferences) {
  const titles = preferences?.job_titles ?? [];
  const locations = preferences?.locations ?? [];

  const unmatchedTitles = titles.filter(
    (title) =>
      !jobs.some((job) => matchesJobTitle(job, title))
  );

  const unmatchedLocations = locations.filter(
    (location) =>
      !jobs.some((job) => matchesJobLocation(job, location))
  );

  const hasPreferences =
    titles.length > 0 ||
    locations.length > 0 ||
    (preferences?.workplace_type?.length ?? 0) > 0;

  const noCombinedMatches =
    hasPreferences &&
    !jobs.some((job) =>
      matchesSavedPreferences(job, preferences)
    );

  return {
    unmatchedTitles,
    unmatchedLocations,
    noCombinedMatches,
  };
}