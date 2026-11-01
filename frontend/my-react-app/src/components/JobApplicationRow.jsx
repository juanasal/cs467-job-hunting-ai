import { ChevronRight } from "lucide-react";

export default function JobApplicationRow({ job, onSelect }) {
  const formattedDate = new Date(`${job.date}T12:00:00`).toLocaleDateString(
    "en-US",
    {
      month: "short",
      day: "numeric",
      year: "numeric",
    }
  );

  return (
    <tr>
      <td>
        <div className="company-cell">
          <div className="company-mark">
            {job.company.charAt(0).toUpperCase()}
          </div>
          <div>
            <strong>{job.company}</strong>
            <span>{job.position}</span>
          </div>
        </div>
      </td>

      <td className="muted-cell">{job.location}</td>
      <td className="muted-cell">{formattedDate}</td>

      <td>
        <span
          className={`status-badge ${job.status
            .toLowerCase()
            .replace(" ", "-")}`}
        >
          {job.status}
        </span>
      </td>

      <td>
        <button
          className="icon-button"
          aria-label={`View ${job.company} application`}
          onClick={() => onSelect(job)}
        >
          <ChevronRight size={19} />
        </button>
      </td>
    </tr>
  );
}