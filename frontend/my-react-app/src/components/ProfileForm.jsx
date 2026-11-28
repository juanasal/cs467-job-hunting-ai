/*
GenAI attribution:
Developed with assistance from ChatGPT (OpenAI).
Prompt: Implement JH-020 by extending the existing JH-019
React profile form with education guidance, incomplete-profile
feedback, field-specific validation, and profile completion
status. Extract profile completion validation into a separate
module to avoid React Fast Refresh lint warnings. Preserve
the existing FastAPI integration, CSRF handling, skills
management, and loading/saving behavior.
Reviewed and adapted for the CS467 Job Hunting AI project.
*/

import { useEffect, useState } from "react";
import { CheckCircle2, Info, Plus, Save, X } from "lucide-react";
import { apiFetch } from "../api";
import { getMissingProfileFields } from "./profileCompletion";

const EDUCATION_OPTIONS = [
  { value: "high_school", label: "High School" },
  { value: "associate", label: "Associate Degree" },
  { value: "bachelor", label: "Bachelor's Degree" },
  { value: "master", label: "Master's Degree" },
  { value: "doctorate", label: "Doctorate" },
  { value: "other", label: "Other" },
];

const EXPERIENCE_OPTIONS = [
  { value: "entry", label: "Entry Level" },
  { value: "mid", label: "Mid Level" },
  { value: "senior", label: "Senior Level" },
];

function getErrorMessage(data, fallback) {
  if (typeof data?.error?.message === "string") {
    return data.error.message;
  }

  if (typeof data?.detail === "string") {
    return data.detail;
  }

  return fallback;
}

export default function ProfileForm({ onSessionExpired }) {
  const [skills, setSkills] = useState([]);
  const [skillInput, setSkillInput] = useState("");
  const [educationLevel, setEducationLevel] = useState("");
  const [experienceLevel, setExperienceLevel] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const missingFields = getMissingProfileFields({
    skills,
    educationLevel,
    experienceLevel,
  });

  const isComplete = missingFields.length === 0;

  useEffect(() => {
    const controller = new AbortController();

    async function fetchProfile() {
      try {
        const response = await apiFetch("/api/profile", {
          signal: controller.signal,
        });

        if (controller.signal.aborted) return;

        if (response.status === 401) {
          onSessionExpired?.();
          throw new Error("Please log in to view your profile.");
        }

        if (response.status === 404) {
          setSkills([]);
          setEducationLevel("");
          setExperienceLevel("");
          setSaved(false);
          return;
        }

        const data = await response.json();

        if (controller.signal.aborted) return;

        if (!response.ok) {
          throw new Error(
            getErrorMessage(data, "Unable to load your profile.")
          );
        }

        setSkills(data.skills ?? []);
        setEducationLevel(data.education_level ?? "");
        setExperienceLevel(data.experience_level ?? "");
        setSaved(true);
      } catch (err) {
        if (!controller.signal.aborted) {
          setError(err.message || "Unable to load your profile.");
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }

    fetchProfile();

    return () => controller.abort();
  }, []);

  function clearFeedback() {
    setError("");
    setMessage("");
    setSaved(false);
  }

  function addSkill() {
    const normalized = skillInput.trim().replace(/\s+/g, " ");

    clearFeedback();

    if (!normalized || normalized.length > 100) {
      setError("Each skill must contain 1 to 100 characters.");
      return;
    }

    if (
      skills.some(
        (skill) => skill.toLowerCase() === normalized.toLowerCase()
      )
    ) {
      setError("This skill has already been added.");
      return;
    }

    setSkills((current) => [...current, normalized]);
    setSkillInput("");
  }

  function removeSkill(skillToRemove) {
    setSkills((current) =>
      current.filter((skill) => skill !== skillToRemove)
    );
    clearFeedback();
  }

  function handleSkillKeyDown(event) {
    if (event.key === "Enter") {
      event.preventDefault();
      addSkill();
    }
  }

  async function handleSave(event) {
    event.preventDefault();
    setError("");
    setMessage("");

    if (!isComplete) {
      setError(
        `Please complete the following: ${missingFields.join(" ")}`
      );
      return;
    }

    setSaving(true);

    try {
      const response = await apiFetch("/api/profile", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          skills,
          education_level: educationLevel,
          experience_level: experienceLevel,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        if (response.status === 401) {
          onSessionExpired?.();
          throw new Error("Please log in to save your profile.");
        }

        throw new Error(
          getErrorMessage(data, "Unable to save your profile.")
        );
      }

      setSkills(data.skills ?? []);
      setEducationLevel(data.education_level ?? "");
      setExperienceLevel(data.experience_level ?? "");
      setSaved(true);
      setMessage("Your profile has been saved successfully.");
    } catch (err) {
      setSaved(false);
      setError(err.message || "Unable to save your profile.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="profile-form-card">
      <h2>Skills, Education and Experience</h2>

      <p className="profile-form-description">
        Add your background information to improve job matching.
        Education and experience are based on the information
        you provide and are not independently verified.
      </p>

      {loading ? (
        <p role="status">Loading your profile...</p>
      ) : (
        <form onSubmit={handleSave}>
          {missingFields.length > 0 ? (
            <div
              className="profile-completion-notice"
              role="status"
              aria-live="polite"
            >
              <div className="profile-completion-heading">
                <Info size={18} aria-hidden="true" />
                <strong>Complete your profile</strong>
              </div>

              <p>
                To get more accurate job matches, please:
              </p>

              <ul>
                {missingFields.map((field) => (
                  <li key={field}>{field}</li>
                ))}
              </ul>
            </div>
          ) : (
            <div
              className="profile-completion-success"
              role="status"
              aria-live="polite"
            >
              <CheckCircle2 size={18} aria-hidden="true" />
              <span>
                {saved
                  ? "Your profile is complete and saved."
                  : "All required fields are filled. Save your changes."}
              </span>
            </div>
          )}

          <div className="profile-form-field">
            <label htmlFor="profile-skill-input">Skills</label>

            <div className="profile-skills-list">
              {skills.map((skill) => (
                <span className="profile-skill-tag" key={skill}>
                  {skill}

                  <button
                    type="button"
                    onClick={() => removeSkill(skill)}
                    aria-label={`Remove ${skill}`}
                    disabled={saving}
                  >
                    <X size={14} />
                  </button>
                </span>
              ))}
            </div>

            <div className="profile-add-skill">
              <input
                id="profile-skill-input"
                value={skillInput}
                onChange={(event) => {
                  setSkillInput(event.target.value);
                  clearFeedback();
                }}
                onKeyDown={handleSkillKeyDown}
                placeholder="e.g. Python, SQL, React"
                maxLength={100}
                disabled={saving}
              />

              <button
                type="button"
                onClick={addSkill}
                className="primary-button"
                disabled={saving}
              >
                <Plus size={16} />
                Add
              </button>
            </div>

            <p className="profile-field-hint">
              Add skills one at a time. Duplicate skills are not allowed.
            </p>
          </div>

          <div className="profile-form-field">
            <label htmlFor="profile-education">
              Education Level
            </label>

            <select
              id="profile-education"
              value={educationLevel}
              disabled={saving}
              onChange={(event) => {
                setEducationLevel(event.target.value);
                clearFeedback();
              }}
            >
              <option value="">Select education level</option>

              {EDUCATION_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>

            <p className="profile-field-hint">
              Select your highest completed education level.
            </p>
          </div>

          <div className="profile-form-field">
            <label htmlFor="profile-experience">
              Experience Level
            </label>

            <select
              id="profile-experience"
              value={experienceLevel}
              disabled={saving}
              onChange={(event) => {
                setExperienceLevel(event.target.value);
                clearFeedback();
              }}
            >
              <option value="">Select experience level</option>

              {EXPERIENCE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>

            <p className="profile-field-hint">
              Choose the level that best describes your work experience.
            </p>
          </div>

          {error && (
            <p className="profile-form-error" role="alert">
              {error}
            </p>
          )}

          {message && (
            <p className="profile-form-success" role="status">
              {message}
            </p>
          )}

          <button
            type="submit"
            className="primary-button profile-save-button"
            disabled={saving}
          >
            <Save size={17} />
            {saving ? "Saving..." : "Save Changes"}
          </button>
        </form>
      )}
    </section>
  );
}
