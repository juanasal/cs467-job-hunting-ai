import { Briefcase, MapPin, DollarSign, GraduationCap } from "lucide-react";

export default function JobPostingCard({ job, onTrack }) {
  // Format numeric salary to USD currency (e.g. $85,000)
  const formattedSalary = job.salary
    ? new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: "USD",
        maximumFractionDigits: 0,
      }).format(job.salary)
    : null;

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
          <span>{job.workplace}</span>
          <span>{job.experience}</span>
          {job.education && (
            <span>
              <GraduationCap size={13} />
              {job.education}
            </span>
          )}
          {formattedSalary && (
            <span>
              <DollarSign size={13} />
              {formattedSalary} / yr
            </span>
          )}
        </div>
      </div>

      <button className="secondary-button" onClick={() => onTrack(job)}>
        Track application
      </button>
    </article>
  );
}