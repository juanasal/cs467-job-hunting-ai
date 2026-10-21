import { Briefcase, MapPin } from "lucide-react";

export default function JobPostingCard({ job, onTrack }) {
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
        </div>
      </div>

      <button className="secondary-button" onClick={() => onTrack(job)}>
        Track application
      </button>
    </article>
  );
}