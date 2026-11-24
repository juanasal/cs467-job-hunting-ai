/*
GenAI attribution:
Developed with assistance from ChatGPT (OpenAI).
Prompt: Implement JH-021 search preference controls using the
existing FastAPI preferences API and authenticated apiFetch helper.
Support multiple job titles, locations, and workplace types,
validation, loading, saving, and error handling. Preserve unrelated
preferences and reject unsupported values without silently changing
the user's selected search restrictions.

Follow-up prompt: Address PR review feedback by displaying
field-level FastAPI validation errors from error.details instead
of only showing the generic "Request validation failed" message.

Reviewed and adapted for the CS467 Job Hunting AI project.
*/

import { useEffect, useState } from "react";
import { Plus, Save, X } from "lucide-react";
import { apiFetch } from "../api";

const WORKPLACE_OPTIONS = [
  { value: "remote", label: "Remote" },
  { value: "hybrid", label: "Hybrid" },
  { value: "onsite", label: "On-site" },
];

const DEFAULT_PREFERENCES = {
  job_titles: [],
  locations: [],
  workplace_type: [],
  salary_min: null,
  salary_max: null,
  salary_currency: "USD",
  result_count: 20,
};

// JH-021: Show field-level API validation errors.
// Updated with assistance from ChatGPT (OpenAI).
function getErrorMessage(data, fallback) {
  const details = data?.error?.details;

  if (Array.isArray(details) && details.length > 0) {
    return details
      .map((item) => {
        const field = Array.isArray(item.loc)
          ? item.loc
              .filter((part) => part !== "body")
              .join(".")
          : "Preference";

        const message =
          typeof item.message === "string"
            ? item.message
            : "Invalid value.";

        return `${field || "Preference"}: ${message}`;
      })
      .join(" ");
  }

  if (typeof data?.error?.message === "string") {
    return data.error.message;
  }

  if (typeof data?.detail === "string") {
    return data.detail;
  }

  if (Array.isArray(data?.detail)) {
    return data.detail
      .map((item) => item.msg || "Invalid preference value.")
      .join(" ");
  }

  return fallback;
}

function validateEntries(values, label) {
  if (!Array.isArray(values)) {
    return `${label} must be a list.`;
  }

  const seen = new Set();

  for (const value of values) {
    if (typeof value !== "string") {
      return `${label} contains an invalid value.`;
    }

    if (!value.trim() || value.length > 255) {
      return `${label} entries must contain 1 to 255 characters.`;
    }

    const key = value.trim().toLowerCase();

    if (seen.has(key)) {
      return `Duplicate ${label.toLowerCase()} are not allowed.`;
    }

    seen.add(key);
  }

  return "";
}

function validatePreferences(preferences) {
  const titleError = validateEntries(
    preferences.job_titles,
    "Job titles"
  );

  if (titleError) return titleError;

  const locationError = validateEntries(
    preferences.locations,
    "Locations"
  );

  if (locationError) return locationError;

  if (!Array.isArray(preferences.workplace_type)) {
    return "Workplace preferences must be a list.";
  }

  const allowedTypes = WORKPLACE_OPTIONS.map(
    (option) => option.value
  );

  const selectedTypes = preferences.workplace_type;

  if (
    selectedTypes.some(
      (type) => !allowedTypes.includes(type)
    )
  ) {
    return "Unsupported workplace preference found. Please review your saved settings.";
  }

  if (
    new Set(selectedTypes).size !==
    selectedTypes.length
  ) {
    return "Duplicate workplace preferences are not allowed.";
  }

  return "";
}

export default function SearchPreferencesForm() {
  const [preferences, setPreferences] = useState(
    DEFAULT_PREFERENCES
  );

  const [titleInput, setTitleInput] = useState("");
  const [locationInput, setLocationInput] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    const controller = new AbortController();

    async function loadPreferences() {
      try {
        const response = await apiFetch(
          "/api/preferences",
          {
            signal: controller.signal,
          }
        );

        if (controller.signal.aborted) return;

        if (response.status === 401) {
          throw new Error(
            "Please log in to view your preferences."
          );
        }

        if (response.status === 404) {
          return;
        }

        const data = await response.json();

        if (controller.signal.aborted) return;

        if (!response.ok) {
          throw new Error(
            getErrorMessage(
              data,
              "Unable to load search preferences."
            )
          );
        }

        const loaded = {
          ...DEFAULT_PREFERENCES,
          ...data,
        };

        const validationError =
          validatePreferences(loaded);

        if (validationError) {
          throw new Error(validationError);
        }

        setPreferences(loaded);
      } catch (err) {
        if (!controller.signal.aborted) {
          setError(
            err.message ||
              "Unable to load search preferences."
          );
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }

    loadPreferences();

    return () => controller.abort();
  }, []);

  function clearFeedback() {
    setError("");
    setMessage("");
  }

  function addEntry(
    field,
    input,
    setInput,
    label
  ) {
    clearFeedback();

    const normalized = input
      .trim()
      .replace(/\s+/g, " ");

    if (
      !normalized ||
      normalized.length > 255
    ) {
      setError(
        `${label} must contain 1 to 255 characters.`
      );
      return;
    }

    if (
      preferences[field].some(
        (value) =>
          value.toLowerCase() ===
          normalized.toLowerCase()
      )
    ) {
      setError(
        `This ${label.toLowerCase()} has already been added.`
      );
      return;
    }

    setPreferences((current) => ({
      ...current,
      [field]: [
        ...current[field],
        normalized,
      ],
    }));

    setInput("");
  }

  function removeEntry(field, value) {
    clearFeedback();

    setPreferences((current) => ({
      ...current,
      [field]: current[field].filter(
        (item) => item !== value
      ),
    }));
  }

  function toggleWorkplace(type) {
    clearFeedback();

    setPreferences((current) => ({
      ...current,
      workplace_type:
        current.workplace_type.includes(type)
          ? current.workplace_type.filter(
              (item) => item !== type
            )
          : [
              ...current.workplace_type,
              type,
            ],
    }));
  }

  async function handleSave(event) {
    event.preventDefault();
    clearFeedback();

    if (
      titleInput.trim() ||
      locationInput.trim()
    ) {
      setError(
        "Please add your entered job title or location before saving."
      );
      return;
    }

    const validationError =
      validatePreferences(preferences);

    if (validationError) {
      setError(validationError);
      return;
    }

    setSaving(true);

    try {
      const response = await apiFetch(
        "/api/preferences",
        {
          method: "PUT",
          headers: {
            "Content-Type":
              "application/json",
          },
          body: JSON.stringify({
            job_titles:
              preferences.job_titles,
            locations:
              preferences.locations,
            workplace_type:
              preferences.workplace_type,
            salary_min:
              preferences.salary_min,
            salary_max:
              preferences.salary_max,
            salary_currency:
              preferences.salary_currency,
            result_count:
              preferences.result_count,
          }),
        }
      );

      const data = await response
        .json()
        .catch(() => ({}));

      if (!response.ok) {
        if (response.status === 401) {
          throw new Error(
            "Please log in to save your preferences."
          );
        }

        throw new Error(
          getErrorMessage(
            data,
            "Unable to save search preferences."
          )
        );
      }

      setPreferences({
        ...DEFAULT_PREFERENCES,
        ...data,
      });

      setMessage(
        "Your search preferences have been saved successfully."
      );
    } catch (err) {
      setError(
        err.message ||
          "Unable to save search preferences."
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="profile-form-card search-preferences-card">
      <h2>Job Search Preferences</h2>

      <p className="profile-form-description">
        Choose the jobs and work locations
        you are interested in.
      </p>

      {loading ? (
        <p role="status">
          Loading search preferences...
        </p>
      ) : (
        <form onSubmit={handleSave}>
          <div className="profile-form-field">
            <label htmlFor="preference-title-input">
              Preferred Job Titles
            </label>

            <div className="profile-skills-list">
              {preferences.job_titles.map(
                (title) => (
                  <span
                    className="profile-skill-tag"
                    key={title}
                  >
                    {title}

                    <button
                      type="button"
                      onClick={() =>
                        removeEntry(
                          "job_titles",
                          title
                        )
                      }
                      aria-label={`Remove ${title}`}
                      disabled={saving}
                    >
                      <X size={14} />
                    </button>
                  </span>
                )
              )}
            </div>

            <div className="profile-add-skill">
              <input
                id="preference-title-input"
                value={titleInput}
                maxLength={255}
                placeholder="e.g. Software Engineer"
                disabled={saving}
                onChange={(event) => {
                  setTitleInput(
                    event.target.value
                  );
                  clearFeedback();
                }}
                onKeyDown={(event) => {
                  if (
                    event.key === "Enter"
                  ) {
                    event.preventDefault();

                    addEntry(
                      "job_titles",
                      titleInput,
                      setTitleInput,
                      "Job title"
                    );
                  }
                }}
              />

              <button
                type="button"
                className="primary-button"
                disabled={saving}
                onClick={() =>
                  addEntry(
                    "job_titles",
                    titleInput,
                    setTitleInput,
                    "Job title"
                  )
                }
              >
                <Plus size={16} />
                Add
              </button>
            </div>
          </div>

          <div className="profile-form-field">
            <label htmlFor="preference-location-input">
              Preferred Locations
            </label>

            <div className="profile-skills-list">
              {preferences.locations.map(
                (location) => (
                  <span
                    className="profile-skill-tag"
                    key={location}
                  >
                    {location}

                    <button
                      type="button"
                      onClick={() =>
                        removeEntry(
                          "locations",
                          location
                        )
                      }
                      aria-label={`Remove ${location}`}
                      disabled={saving}
                    >
                      <X size={14} />
                    </button>
                  </span>
                )
              )}
            </div>

            <div className="profile-add-skill">
              <input
                id="preference-location-input"
                value={locationInput}
                maxLength={255}
                placeholder="e.g. Los Angeles, CA"
                disabled={saving}
                onChange={(event) => {
                  setLocationInput(
                    event.target.value
                  );
                  clearFeedback();
                }}
                onKeyDown={(event) => {
                  if (
                    event.key === "Enter"
                  ) {
                    event.preventDefault();

                    addEntry(
                      "locations",
                      locationInput,
                      setLocationInput,
                      "Location"
                    );
                  }
                }}
              />

              <button
                type="button"
                className="primary-button"
                disabled={saving}
                onClick={() =>
                  addEntry(
                    "locations",
                    locationInput,
                    setLocationInput,
                    "Location"
                  )
                }
              >
                <Plus size={16} />
                Add
              </button>
            </div>
          </div>

          <fieldset className="preference-workplace-fieldset">
            <legend>
              Workplace Type
            </legend>

            <p className="profile-field-hint">
              Select all workplace types
              you are willing to consider.
              Your choices will not be
              automatically expanded.
            </p>

            <div className="preference-workplace-options">
              {WORKPLACE_OPTIONS.map(
                (option) => (
                  <label
                    key={option.value}
                  >
                    <input
                      type="checkbox"
                      checked={preferences.workplace_type.includes(
                        option.value
                      )}
                      disabled={saving}
                      onChange={() =>
                        toggleWorkplace(
                          option.value
                        )
                      }
                    />

                    <span>
                      {option.label}
                    </span>
                  </label>
                )
              )}
            </div>
          </fieldset>

          {error && (
            <p
              className="profile-form-error"
              role="alert"
            >
              {error}
            </p>
          )}

          {message && (
            <p
              className="profile-form-success"
              role="status"
            >
              {message}
            </p>
          )}

          <button
            type="submit"
            className="primary-button profile-save-button"
            disabled={saving}
          >
            <Save size={17} />
            {saving
              ? "Saving..."
              : "Save Preferences"}
          </button>
        </form>
      )}
    </section>
  );
}
