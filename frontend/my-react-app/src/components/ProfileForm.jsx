
/*
GenAI attribution:
Developed with assistance from ChatGPT (OpenAI).
Prompt: Implement the JH-019 React profile form using the
existing FastAPI profile endpoints, including skill validation,
education and experience fields, CSRF protection, loading,
saving, and error handling. Refine the loading effect to avoid
React set-state-in-effect warnings.
Reviewed and adapted for the CS467 Job Hunting AI project.
*/

import { useEffect, useState } from "react";
import { Plus, Save, X } from "lucide-react";
import { apiFetch } from "../api";

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

export default function ProfileForm() {
  const [skills, setSkills] = useState([]);
  const [skillInput, setSkillInput] = useState("");
  const [educationLevel, setEducationLevel] = useState("");
  const [experienceLevel, setExperienceLevel] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();

    async function fetchProfile() {
      try {
        const response = await apiFetch("/api/profile", {
          signal: controller.signal,
        });

        if (controller.signal.aborted) return;

        if (response.status === 401) {
          throw new Error("Please log in to view your profile.");
        }

        if (response.status === 404) {
          setSkills([]);
          setEducationLevel("");
          setExperienceLevel("");
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
    clearFeedback();

    if (skills.length === 0) {
      setError("Please add at least one skill.");
      return;
    }

    if (!educationLevel || !experienceLevel) {
      setError("Please select your education and experience levels.");
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
          throw new Error("Please log in to save your profile.");
        }

        throw new Error(
          getErrorMessage(data, "Unable to save your profile.")
        );
      }

      setSkills(data.skills ?? []);
      setEducationLevel(data.education_level ?? "");
      setExperienceLevel(data.experience_level ?? "");
      setMessage("Your profile has been saved successfully.");
    } catch (err) {
      setError(err.message || "Unable to save your profile.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="profile-form-card">
      <h2>Skills and Experience</h2>

      <p className="profile-form-description">
        Add your background information to improve job matching.
      </p>

      {loading ? (
        <p role="status">Loading your profile...</p>
      ) : (
        <form onSubmit={handleSave}>
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
