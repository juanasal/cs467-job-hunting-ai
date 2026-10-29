
import { Briefcase, MapPin, DollarSign } from "lucide-react";

export default function JobPostingCard({ job, onTrack }) {
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

  return (
    <article className="posting-card">
      <div className="posting-company-icon">
        <Briefcase size={21} />
      </div>

      <div className="posting-info">
        <h3>{job.title}</h3>
        <p>{job.company}</p>

        <div className="posting-tags">
          <span>
            <MapPin size={13} />
            {job.location}
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
      </div>

      <button
        className="secondary-button"
        onClick={() => onTrack(job)}
      >
        Track application
      </button>
    </article>
  );
}
