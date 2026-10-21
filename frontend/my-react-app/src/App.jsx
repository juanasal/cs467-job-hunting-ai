import { useMemo, useState } from "react";
import {
  BriefcaseBusiness,
  Search,
  Clock3,
  CircleCheck,
  XCircle,
  Menu,
  MapPin,
  UserRound,
} from "lucide-react";

import { initialApplications } from "./data/applications";
import { jobPostings } from "./data/jobPostings";

import Sidebar from "./components/Sidebar";
import StatCard from "./components/StatCard";
import JobApplicationRow from "./components/JobApplicationRow";
import JobPostingCard from "./components/JobPostingCard";

import "./App.css";

export default function App() {
  const [activePage, setActivePage] = useState("Dashboard");
  const [jobs, setJobs] = useState(initialApplications);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("All Statuses");
  const [selectedJob, setSelectedJob] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [loggedIn, setLoggedIn] = useState(false);

  // Job Search Filters
  const [jobTitleSearch, setJobTitleSearch] = useState("");
  const [jobLocation, setJobLocation] = useState("");
  const [workplaceType, setWorkplaceType] = useState("Any type");
  const [education, setEducation] = useState("Any education");
  const [minSalary, setMinSalary] = useState(50000);
  const [maxSalary, setMaxSalary] = useState(150000);

  // Helper function to format salary for display
  const formatSalaryLabel = (val) =>
    new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      maximumFractionDigits: 0,
    }).format(val);

  // Filtering Available Job Postings
  const filteredAvailableJobs = jobPostings.filter((job) => {
    const matchesTitle = job.title
      .toLowerCase()
      .includes(jobTitleSearch.toLowerCase());

    const matchesLocation = job.location
      .toLowerCase()
      .includes(jobLocation.toLowerCase());

    const matchesWorkplace =
      workplaceType === "Any type" || job.workplace === workplaceType;

    const matchesEducation =
      education === "Any education" || job.education === education;

    const matchesSalary =
      !job.salary || (job.salary >= minSalary && job.salary <= maxSalary);

    return (
      matchesTitle &&
      matchesLocation &&
      matchesWorkplace &&
      matchesEducation &&
      matchesSalary
    );
  });

  const statuses = ["Applied", "In Progress", "Interview", "Offer", "Rejected"];

  const filteredJobs = useMemo(() => {
    return jobs.filter((job) => {
      const term = search.toLowerCase();
      const matchesSearch =
        job.company.toLowerCase().includes(term) ||
        job.position.toLowerCase().includes(term) ||
        job.location.toLowerCase().includes(term);

      const matchesStatus = filter === "All Statuses" || job.status === filter;

      return matchesSearch && matchesStatus;
    });
  }, [jobs, search, filter]);

  const counts = {
    total: jobs.length,
    progress: jobs.filter((j) =>
      ["Applied", "In Progress", "Interview"].includes(j.status)
    ).length,
    offers: jobs.filter((j) => j.status === "Offer").length,
    rejected: jobs.filter((j) => j.status === "Rejected").length,
  };

  function navigate(page) {
    setActivePage(page);
    setSidebarOpen(false);
    setSelectedJob(null);
  }

  function updateStatus(id, status) {
    setJobs((current) =>
      current.map((job) => (job.id === id ? { ...job, status } : job))
    );
    setSelectedJob((current) =>
      current?.id === id ? { ...current, status } : current
    );
  }

  function handleTrackJob(job) {
    const alreadyApplied = jobs.some(
      (application) =>
        application.company === job.company && application.position === job.title
    );

    if (alreadyApplied) {
      window.alert("You have already added this application.");
      return;
    }

    setJobs((current) => [
      {
        id: Date.now(),
        company: job.company,
        position: job.title,
        location: job.location,
        date: new Date().toISOString().slice(0, 10),
        status: "Applied",
      },
      ...current,
    ]);
    navigate("Applied Jobs");
  }

  return (
    <div className="app-shell">
      {sidebarOpen && (
        <button
          className="mobile-overlay"
          aria-label="Close navigation"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <Sidebar
        activePage={activePage}
        onNavigate={navigate}
        loggedIn={loggedIn}
        onToggleLogin={() => setLoggedIn((value) => !value)}
        sidebarOpen={sidebarOpen}
      />

      <main className="main-content">
        <header className="topbar">
          <button
            className="mobile-menu"
            aria-label="Open navigation"
            onClick={() => setSidebarOpen(true)}
          >
            <Menu size={22} />
          </button>
          <span className="breadcrumb">Workspace / {activePage}</span>
          <div className="topbar-right">
            <span className="topbar-label">JOB APPLICATIONS</span>
            <div className="avatar small-avatar">U</div>
          </div>
        </header>

        {activePage === "Job Postings" ? (
          <section className="postings-page">
            <div className="page-heading postings-heading">
              <div>
                <p className="eyebrow">EXPLORE OPPORTUNITIES</p>
                <h1>Job Postings</h1>
                <p className="page-description">
                  Find opportunities that match your career goals.
                </p>
              </div>
            </div>

            <section className="postings-panel">
              <h2>Find your next role</h2>
              <p className="postings-subtitle">
                Search job titles and narrow down your results.
              </p>

              <label htmlFor="job-title-search">Job title</label>
              <div className="posting-search">
                <Search size={19} />
                <input
                  id="job-title-search"
                  placeholder="Search job titles, e.g. Data Analyst"
                  value={jobTitleSearch}
                  onChange={(e) => setJobTitleSearch(e.target.value)}
                />
              </div>

              <div className="posting-filters">
                <div className="filter-field">
                  <label htmlFor="education-filter">Education level</label>
                  <select
                    id="education-filter"
                    value={education}
                    onChange={(e) => setEducation(e.target.value)}
                  >
                    <option>Any education</option>
                    <option>High School</option>
                    <option>Associate's</option>
                    <option>Bachelor's</option>
                    <option>Master's</option>
                    <option>Doctorate</option>
                  </select>
                </div>

                <div className="filter-field">
                  <label htmlFor="workplace-filter">Workplace type</label>
                  <select
                    id="workplace-filter"
                    value={workplaceType}
                    onChange={(e) => setWorkplaceType(e.target.value)}
                  >
                    <option>Any type</option>
                    <option>Remote</option>
                    <option>Hybrid</option>
                    <option>On-site</option>
                  </select>
                </div>

                <div className="filter-field">
                  <label htmlFor="location-filter">Location</label>
                  <div className="posting-search location-search">
                    <MapPin size={18} />
                    <input
                      id="location-filter"
                      placeholder="City, state, or remote"
                      value={jobLocation}
                      onChange={(e) => setJobLocation(e.target.value)}
                    />
                  </div>
                </div>

                <div className="filter-field slider-filter-field">
                  <label>
                    Min Salary: <strong>{formatSalaryLabel(minSalary)}</strong>
                  </label>
                  <input
                    type="range"
                    min="30000"
                    max="150000"
                    step="5000"
                    value={minSalary}
                    onChange={(e) => {
                      const val = Number(e.target.value);
                      setMinSalary(val);
                      if (val > maxSalary) setMaxSalary(val);
                    }}
                  />
                </div>

                <div className="filter-field slider-filter-field">
                  <label>
                    Max Salary: <strong>{formatSalaryLabel(maxSalary)}</strong>
                  </label>
                  <input
                    type="range"
                    min="30000"
                    max="150000"
                    step="5000"
                    value={maxSalary}
                    onChange={(e) => {
                      const val = Number(e.target.value);
                      setMaxSalary(val);
                      if (val < minSalary) setMinSalary(val);
                    }}
                  />
                </div>
              </div>

              <div className="posting-results-header">
                <h2>Matching jobs</h2>
                <span>{filteredAvailableJobs.length} results</span>
              </div>

              <div className="posting-results">
                {filteredAvailableJobs.map((job) => (
                  <JobPostingCard
                    key={job.id}
                    job={job}
                    onTrack={handleTrackJob}
                  />
                ))}

                {filteredAvailableJobs.length === 0 && (
                  <p className="postings-empty">
                    No matching jobs. Try changing your search or filters.
                  </p>
                )}
              </div>
            </section>
          </section>
        ) : activePage === "Dashboard" || activePage === "Applied Jobs" ? (
          <>
            <section className="page-heading">
              <div>
                <p className="eyebrow">YOUR CAREER WORKSPACE</p>
                <h1>
                  {activePage === "Dashboard" ? "Dashboard" : "Applied Jobs"}
                </h1>
                <p className="page-description">
                  Keep track of your applications and next steps.
                </p>
              </div>
            </section>

            {activePage === "Dashboard" && (
              <section className="stats-grid">
                <StatCard
                  icon={<BriefcaseBusiness />}
                  label="Total Applications"
                  value={counts.total}
                  note="All tracked applications"
                  color="blue"
                />
                <StatCard
                  icon={<Clock3 />}
                  label="In Progress"
                  value={counts.progress}
                  note="Applied, interviews and reviews"
                  color="amber"
                />
                <StatCard
                  icon={<CircleCheck />}
                  label="Offers"
                  value={counts.offers}
                  note="Potential opportunities"
                  color="green"
                />
                <StatCard
                  icon={<XCircle />}
                  label="Rejected"
                  value={counts.rejected}
                  note="Applications not selected"
                  color="red"
                />
              </section>
            )}

            <section className="jobs-panel">
              <div className="panel-header">
                <div>
                  <h2>
                    {activePage === "Dashboard"
                      ? "Recent Applications"
                      : "All Applications"}
                  </h2>
                  <p>Review and update your job search progress.</p>
                </div>
                <span className="results-count">{filteredJobs.length} jobs</span>
              </div>

              <div className="table-toolbar">
                <div className="search-box">
                  <Search size={18} />
                  <input
                    aria-label="Search jobs"
                    placeholder="Search company, title or location..."
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                  />
                </div>
                <select
                  aria-label="Filter by status"
                  value={filter}
                  onChange={(e) => setFilter(e.target.value)}
                >
                  <option>All Statuses</option>
                  {statuses.map((status) => (
                    <option key={status}>{status}</option>
                  ))}
                </select>
              </div>

              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Company / Role</th>
                      <th>Location</th>
                      <th>Applied Date</th>
                      <th>Status</th>
                      <th aria-label="View details" />
                    </tr>
                  </thead>
                  <tbody>
                    {filteredJobs.map((job) => (
                      <JobApplicationRow
                        key={job.id}
                        job={job}
                        onSelect={setSelectedJob}
                      />
                    ))}
                    {filteredJobs.length === 0 && (
                      <tr>
                        <td colSpan="5" className="empty-state">
                          No applications match your search.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </section>
          </>
        ) : (
          <section className="placeholder-page">
            <div className="placeholder-icon">
              <UserRound size={28} />
            </div>
            <p className="eyebrow">ACCOUNT SETTINGS</p>
            <h1>Profile</h1>
            <p>Manage your profile and job search preferences.</p>

            <div className="settings-card">
              <h2>Profile Information</h2>
              <label htmlFor="profile-name">Name</label>
              <input id="profile-name" placeholder="Your name" />

              <label htmlFor="profile-email">Email</label>
              <input
                id="profile-email"
                type="email"
                placeholder="you@example.com"
              />

              <h2>Preferences</h2>
              <label htmlFor="preferred-role">Preferred job role</label>
              <input id="preferred-role" placeholder="e.g. Data Analyst" />

              <label htmlFor="preferred-location">Preferred location</label>
              <input
                id="preferred-location"
                placeholder="e.g. Remote, California"
              />

              <button
                className="primary-button"
                onClick={() =>
                  window.alert("Connect a backend to save profile settings.")
                }
              >
                Save Changes
              </button>
            </div>
          </section>
        )}
      </main>

      {selectedJob && (
        <div className="modal-backdrop" onClick={() => setSelectedJob(null)}>
          <section
            className="job-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="job-modal-title"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-heading">
              <div>
                <p className="eyebrow">APPLICATION DETAILS</p>
                <h2 id="job-modal-title">{selectedJob.company}</h2>
                <p>{selectedJob.position}</p>
              </div>
              <button
                className="icon-button"
                aria-label="Close details"
                onClick={() => setSelectedJob(null)}
              >
                ×
              </button>
            </div>
            <p className="detail-label">Location</p>
            <p>{selectedJob.location}</p>
            <p className="detail-label">Application status</p>
            <select
              value={selectedJob.status}
              onChange={(e) => updateStatus(selectedJob.id, e.target.value)}
            >
              {statuses.map((status) => (
                <option key={status}>{status}</option>
              ))}
            </select>
            <button
              className="primary-button modal-done"
              onClick={() => setSelectedJob(null)}
            >
              Done
            </button>
          </section>
        </div>
      )}
    </div>
  );
}