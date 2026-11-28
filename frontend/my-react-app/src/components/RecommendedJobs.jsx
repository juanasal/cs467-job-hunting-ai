import { useEffect, useState } from "react";

import { apiFetch } from "../api";
import JobPostingCard from "./JobPostingCard";

// The API has no freshness flag, so results count as outdated when the
// most recently retrieved job is older than this many days.
export const OUTDATED_AFTER_DAYS = 7;

const DAY_MS = 24 * 60 * 60 * 1000;

function isOutdated(recommendations) {
  const times = recommendations
    .map((item) => new Date(item.job?.retrieved_at).getTime())
    .filter((time) => !Number.isNaN(time));

  if (times.length === 0) return false;

  return Date.now() - Math.max(...times) > OUTDATED_AFTER_DAYS * DAY_MS;
}

// Ranked job recommendations for the Dashboard (JH-042).
// Jobs are shown in the order GET /api/recommendations returns them.
export default function RecommendedJobs({ signedIn, authLoading, onGoToProfile }) {
  const [recommendations, setRecommendations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!signedIn) return;

    const controller = new AbortController();

    async function loadRecommendations() {
      setLoading(true);
      setError("");
      setRecommendations([]);

      try {
        const response = await apiFetch("/api/recommendations", {
          signal: controller.signal,
        });

        // apiFetch already opens sign-in on a 401.
        if (response.status === 401) return;

        const data = await response.json().catch(() => ({}));

        if (!response.ok || !Array.isArray(data.recommendations)) {
          throw new Error("Bad response");
        }

        if (!controller.signal.aborted) {
          setRecommendations(data.recommendations);
        }
      } catch {
        if (!controller.signal.aborted) {
          setError(
            "We couldn't load your recommended jobs. Check your connection and refresh the page to try again."
          );
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }

    loadRecommendations();

    return () => controller.abort();
  }, [signedIn]);

  let content;

  if (authLoading) {
    content = <p className="postings-empty" role="status">Checking your session...</p>;
  } else if (!signedIn) {
    content = (
      <p className="postings-empty">
        Sign in to see job recommendations ranked for your profile.
      </p>
    );
  } else if (loading) {
    content = <p className="postings-empty" role="status">Loading your recommended jobs...</p>;
  } else if (error) {
    content = <p className="profile-form-error" role="alert">{error}</p>;
  } else if (recommendations.length === 0) {
    content = (
      <div className="postings-empty" role="status">
        <p>
          No recommended jobs yet. To get recommendations, save your skills
          and at least one job title on your profile and preferences page. If
          you've already done that, no current jobs match your preferences.
        </p>
        <button className="secondary-button" onClick={onGoToProfile}>
          Go to profile & preferences
        </button>
      </div>
    );
  } else {
    content = (
      <>
        {isOutdated(recommendations) && (
          <p className="preference-warning" role="status">
            These results may be outdated. None of these jobs were retrieved
            in the last {OUTDATED_AFTER_DAYS} days, so some may no longer be
            open.
          </p>
        )}

        <div className="posting-results">
          {recommendations.map(({ job, match }) => (
            <JobPostingCard key={job.job_id} job={job} match={match ?? null} />
          ))}
        </div>

        <p className="adzuna-attribution">
          Jobs by{" "}
          <a href="https://www.adzuna.com" target="_blank" rel="noreferrer">
            The Adzuna API
          </a>
        </p>
      </>
    );
  }

  return (
    <section className="jobs-panel" aria-labelledby="recommended-jobs-title">
      <div className="panel-header">
        <div>
          <h2 id="recommended-jobs-title">Recommended Jobs</h2>
          <p>Ranked by fit score, best match first.</p>
        </div>

        {signedIn && !loading && !error && recommendations.length > 0 && (
          <span className="results-count">{recommendations.length} jobs</span>
        )}
      </div>

      <div className="recommended-jobs-body">{content}</div>
    </section>
  );
}
