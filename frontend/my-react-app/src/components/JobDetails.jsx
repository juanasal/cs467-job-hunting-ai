import { useEffect, useState } from "react";

import { apiFetch } from "../api";

// Only http(s) links are shown, so a "javascript:" or other unsafe URL
// can never be opened from the details page.
function safeJobUrl(url) {
  try {
    const parsed = new URL(url);
    return ["http:", "https:"].includes(parsed.protocol) ? parsed.href : null;
  } catch {
    return null;
  }
}

function errorMessage(status) {
  if (status === 404) return "This job couldn't be found. It may have been removed.";
  if (status === 422) return "This job link isn't valid.";
  return "We couldn't load this job. Check your connection and try again.";
}

// Job details page opened from a Dashboard recommendation (JH-043).
// Loads GET /api/jobs/{job_id}. All posting text is rendered as plain
// text through JSX, so nothing in it can run as HTML or script.
export default function JobDetails({ jobId, onBack }) {
  const [details, setDetails] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();

    async function loadJob() {
      setLoading(true);
      setError("");
      setDetails(null);

      try {
        const response = await apiFetch(`/api/jobs/${encodeURIComponent(jobId)}`, {
          signal: controller.signal,
        });

        // apiFetch already opens sign-in on a 401.
        if (response.status === 401) return;

        const data = await response.json().catch(() => ({}));

        if (!response.ok || !data.job) {
          if (!controller.signal.aborted) setError(errorMessage(response.status));
          return;
        }

        if (!controller.signal.aborted) setDetails(data);
      } catch {
        if (!controller.signal.aborted) setError(errorMessage());
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }

    loadJob();

    return () => controller.abort();
  }, [jobId]);

  const backButton = (
    <button className="secondary-button" onClick={onBack}>
      Back to dashboard
    </button>
  );

  let content;

  if (loading) {
    content = <p className="postings-empty" role="status">Loading job details...</p>;
  } else if (error) {
    content = (
      <div className="postings-empty">
        <p className="profile-form-error" role="alert">{error}</p>
        {backButton}
      </div>
    );
  } else if (details) {
    const { job, match } = details;
    const description = job.description?.trim();
    const postingUrl = safeJobUrl(job.job_url);

    content = (
      <>
        {backButton}

        <h3 className="job-details-title">{job.title || "Job title not listed"}</h3>
        <p>{job.company || "Company not listed"}</p>
        <p>{job.location || "Location not listed"}</p>

        <p className="detail-label">Why it matches</p>
        <p>
          {match?.match_explanation ||
            "No match explanation is available for this job."}
        </p>

        <p className="detail-label">Description</p>
        {description ? (
          <>
            {job.source === "adzuna" && (
              <p className="profile-field-hint">
                Shortened description from the source. See the original
                posting for the full text.
              </p>
            )}
            <p className="job-details-description">{description}</p>
          </>
        ) : (
          <p>No description is available for this job.</p>
        )}

        <p className="detail-label">Original posting</p>
        {postingUrl ? (
          <a href={postingUrl} target="_blank" rel="noopener noreferrer">
            View the original posting (opens in a new tab)
          </a>
        ) : (
          <p>The original posting isn't available.</p>
        )}

        {job.source === "adzuna" && (
          <p className="adzuna-attribution">
            Jobs by{" "}
            <a href="https://www.adzuna.com" target="_blank" rel="noreferrer">
              The Adzuna API
            </a>
          </p>
        )}
      </>
    );
  }

  return (
    <section className="jobs-panel" aria-labelledby="job-details-heading">
      <div className="panel-header">
        <div>
          <h2 id="job-details-heading">Job Details</h2>
        </div>
      </div>

      <div className="recommended-jobs-body">{content}</div>
    </section>
  );
}
