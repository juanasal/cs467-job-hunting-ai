import { Briefcase, MapPin, DollarSign } from "lucide-react";

// Dates from the API are shown in UTC so a "YYYY-MM-DD" posting date
// is not shifted to the previous day in US time zones.
function formatDate(value) {
  if (!value) return null;

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;

  return date.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

export default function JobPostingCard({ job, match, onTrack }) {
  const formatSalary = (amount) =>
    new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      maximumFractionDigits: 0,
    }).format(amount);

  const salaryLabel = (() => {
    const min = job.salary_min;
    const max = job.salary_max;

    if (min != null && max != null) {
      return min === max
        ? formatSalary(min)
        : `${formatSalary(min)} – ${formatSalary(max)}`;
    }

    if (min != null) return `${formatSalary(min)}+`;
    if (max != null) return `Up to ${formatSalary(max)}`;

    return null;
  })();

  const workplaceLabels = {
    remote: "Remote",
    hybrid: "Hybrid",
    onsite: "On-site",
  };

  const postedDate = formatDate(job.date_posted);
  const retrievedDate = formatDate(job.retrieved_at);

  return (
    <article className="posting-card">
      <div className="posting-company-icon">
        <Briefcase size={21} />
      </div>

      <div className="posting-info">
        <h3>{job.title || "Job title not listed"}</h3>
        <p>{job.company || "Company not listed"}</p>

        <div className="posting-tags">
          <span>
            <MapPin size={13} />
            {job.location || "Location not listed"}
          </span>

          {job.workplace_type && (
            <span>
              {workplaceLabels[job.workplace_type] ??
                job.workplace_type}
            </span>
          )}

          {salaryLabel && (
            <span>
              <DollarSign size={13} />
              {salaryLabel} / yr
            </span>
          )}
        </div>

        {/* Recommendation details (JH-042). Only shown when a match is passed. */}
        {match !== undefined && (
          <div className="posting-tags posting-match-tags">
            <span>
              {match?.match_score != null
                ? `Fit score: ${Math.round(match.match_score)} / 100`
                : "Fit score not available"}
            </span>

            <span>
              {job.source
                ? `Source: ${job.source.charAt(0).toUpperCase()}${job.source.slice(1)}`
                : "Source not listed"}
            </span>

            <span>
              {postedDate
                ? `Posted ${postedDate}`
                : "Posting date not listed"}
            </span>

            <span>
              {retrievedDate
                ? `Retrieved ${retrievedDate}`
                : "Retrieval date not listed"}
            </span>
          </div>
        )}
      </div>

      {onTrack && (
        <button
          className="secondary-button"
          onClick={() => onTrack(job)}
        >
          Track application
        </button>
      )}
    </article>
  );
}
