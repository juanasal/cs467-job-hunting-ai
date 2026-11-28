/*
GenAI attribution:
Developed with assistance from ChatGPT (OpenAI).
Prompt: Implement JH-022 controlled React inputs for optional
annual USD salary bounds and maximum recommendation count.
Include accessible labels, input limits, and explanations
for missing salary information and recommendation limits.
Reuse existing profile form styles.
Reviewed and adapted for the CS467 Job Hunting AI project.
*/

import {
  MAX_SALARY,
  MAX_RESULT_COUNT,
} from "../data/preferenceLimits";

export default function PreferenceLimitFields({
  preferences,
  onChange,
  disabled = false,
}) {
  return (
    <>
      <fieldset className="preference-salary-fieldset">
        <legend>Preferred Salary Range</legend>

        <p
          id="preference-salary-hint"
          className="profile-field-hint"
        >
          Enter your preferred annual salary in USD.
          Both fields are optional.
        </p>

        <div className="preference-salary-grid">
          <div className="profile-form-field">
            <label htmlFor="preference-salary-min">
              Minimum salary (USD/year)
            </label>

            <input
              id="preference-salary-min"
              type="number"
              min={0}
              max={MAX_SALARY}
              step="0.01"
              placeholder="No minimum"
              value={preferences.salary_min ?? ""}
              disabled={disabled}
              aria-describedby="preference-salary-hint preference-salary-policy"
              onChange={(event) =>
                onChange(
                  "salary_min",
                  event.target.value
                )
              }
            />
          </div>

          <div className="profile-form-field">
            <label htmlFor="preference-salary-max">
              Maximum salary (USD/year)
            </label>

            <input
              id="preference-salary-max"
              type="number"
              min={0}
              max={MAX_SALARY}
              step="0.01"
              placeholder="No maximum"
              value={preferences.salary_max ?? ""}
              disabled={disabled}
              aria-describedby="preference-salary-hint preference-salary-policy"
              onChange={(event) =>
                onChange(
                  "salary_max",
                  event.target.value
                )
              }
            />
          </div>
        </div>

        <p
          id="preference-salary-policy"
          className="profile-field-hint"
        >
          Jobs without salary information may still appear
          in your recommendations, but their salary
          compatibility cannot be verified.
        </p>

        <p className="profile-field-hint">
          {preferences.strict_salary
            ? "Jobs with a confirmed salary mismatch are excluded from recommendations."
            : "Jobs outside your preferred salary range may still be recommended."}
        </p>
      </fieldset>

      <div className="profile-form-field">
        <label htmlFor="preference-result-count">
          Maximum number of recommendations
        </label>

        <input
          id="preference-result-count"
          type="number"
          min={1}
          max={MAX_RESULT_COUNT}
          step={1}
          required
          value={preferences.result_count ?? ""}
          disabled={disabled}
          aria-describedby="preference-result-count-hint"
          onChange={(event) =>
            onChange(
              "result_count",
              event.target.value
            )
          }
        />

        <p
          id="preference-result-count-hint"
          className="profile-field-hint"
        >
          This is the maximum number of recommendations
          requested. Fewer results may be available if
          there are not enough suitable jobs.
        </p>
      </div>
    </>
  );
}