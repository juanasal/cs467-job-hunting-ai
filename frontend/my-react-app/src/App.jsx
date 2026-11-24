import { useEffect, useMemo, useState } from "react";
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

// GenAI attribution:
// Developed with assistance from ChatGPT (OpenAI).
// Prompt: Integrate the JH-019 profile form into the existing React app
// without changing job listings, dashboard, or navigation behavior.
//
// JH-021 follow-up prompt: Address PR review feedback by loading saved
// search preferences and applying them to displayed job postings.
// Preserve strict workplace restrictions, existing search filters,
// authentication, dashboard, and job tracking functionality.
// Reviewed and adapted for the CS467 Job Hunting AI project.
import ProfileForm from "./components/ProfileForm";
import SearchPreferencesForm from "./components/SearchPreferencesForm";
import LoginForm from "./components/LoginForm";
import { apiFetch, setUnauthorizedHandler } from "./api";

import "./App.css";

// Pages that need a signed-in user.
// Add the dashboard here once it uses real user data.
const PRIVATE_PAGES = ["Profile"];

// Where to send the user after signing in if they weren't
// headed to a specific private page.
const DEFAULT_PRIVATE_PAGE = "Profile";

const ALLOWED_WORKPLACE_TYPES = ["remote", "hybrid", "onsite"];

export default function App() {
  const [activePage, setActivePage] = useState("Dashboard");
  const [jobs, setJobs] = useState(initialApplications);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("All Statuses");
  const [selectedJob, setSelectedJob] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [user, setUser] = useState(null);
  const [loginOpen, setLoginOpen] = useState(false);
  const [authLoading, setAuthLoading] = useState(true);
  const [authMessage, setAuthMessage] = useState("");
  const [loggingOut, setLoggingOut] = useState(false);
  const [returnPage, setReturnPage] = useState(null);
  const [loginNotice, setLoginNotice] = useState("");

  useEffect(() => {
    const controller = new AbortController();

    fetch("/api/auth/me", {
      credentials: "include",
      signal: controller.signal,
    })
      .then(async (response) => {
        if (response.status === 401) return null;

        const data = await response.json().catch(() => ({}));

        if (!response.ok) {
          throw new Error(
            data?.error?.message || "Unable to check your session."
          );
        }

        return data.user;
      })
      .then((currentUser) => {
        if (!controller.signal.aborted) {
          setUser(currentUser);
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setAuthMessage(
            "Could not check your sign-in status. You can still try signing in."
          );
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setAuthLoading(false);
        }
      });

    return () => controller.abort();
  }, []);

  // Any 401 from apiFetch means the session is gone:
  // clear signed-in UI and ask to sign in again.
  useEffect(() => {
    setUnauthorizedHandler(() => {
      setUser(null);
      setSelectedJob(null);

      if (PRIVATE_PAGES.includes(activePage)) {
        setReturnPage(activePage);
        setActivePage("Dashboard");
      }

      setLoginNotice("Your session expired. Please sign in again.");
      setLoginOpen(true);
    });

    return () => setUnauthorizedHandler(null);
  }, [activePage]);

  async function handleLogout() {
    setAuthMessage("");
    setLoggingOut(true);

    try {
      const response = await apiFetch("/api/auth/logout", {
        method: "POST",
      });

      const data = await response.json().catch(() => ({}));

      if (response.status === 401) {
        // apiFetch already cleared the UI.
        setLoginOpen(false);
        setLoginNotice("");
        setReturnPage(null);
        setActivePage("Dashboard");
        setAuthMessage("Your session expired. You are signed out.");
        return;
      }

      if (!response.ok) {
        throw new Error(
          data?.error?.message ||
            data?.detail ||
            "Unable to log out. Please try again."
        );
      }

      setUser(null);
      setActivePage("Dashboard");
      setSelectedJob(null);
      setAuthMessage("");
    } catch (err) {
      if (err instanceof TypeError) {
        setAuthMessage(
          "Cannot connect to the server. Check your connection and try again."
        );
      } else {
        setAuthMessage(
          err.message || "Unable to log out. Please try again."
        );
      }
    } finally {
      setLoggingOut(false);
    }
  }

  function handleAuthAction() {
    if (user) {
      handleLogout();
    } else {
      setLoginOpen(true);
    }
  }

  // Job Search Filters
  const [jobTitleSearch, setJobTitleSearch] = useState("");
  const [jobLocation, setJobLocation] = useState("");
  const [workplaceType, setWorkplaceType] = useState("Any type");
  const [minSalary, setMinSalary] = useState(50000);
  const [maxSalary, setMaxSalary] = useState(150000);

  // JH-021 PR review fix:
  // Load saved preferences and apply them to displayed job postings.
  // Developed with assistance from ChatGPT (OpenAI).
  const [savedSearchPreferences, setSavedSearchPreferences] = useState(null);
  const [preferencesLoading, setPreferencesLoading] = useState(false);
  const [preferencesError, setPreferencesError] = useState("");
  const [preferencesChecked, setPreferencesChecked] = useState(false);

  useEffect(() => {
    if (activePage !== "Job Postings" || !user) {
      return;
    }

    const controller = new AbortController();

    async function loadSavedSearchPreferences() {
      setPreferencesLoading(true);
      setPreferencesChecked(false);
      setPreferencesError("");
      setSavedSearchPreferences(null);

      try {
        const response = await apiFetch("/api/preferences", {
          signal: controller.signal,
        });

        if (controller.signal.aborted) return;

        if (response.status === 404) {
          setSavedSearchPreferences(null);
          return;
        }

        const data = await response.json().catch(() => ({}));

        if (controller.signal.aborted) return;

        if (!response.ok) {
          throw new Error(
            data?.error?.message ||
              "Unable to load saved search preferences."
          );
        }

        if (
          !Array.isArray(data.job_titles) ||
          !Array.isArray(data.locations) ||
          !Array.isArray(data.workplace_type) ||
          data.workplace_type.some(
            (type) => !ALLOWED_WORKPLACE_TYPES.includes(type)
          ) ||
          data.job_titles.some((title) => typeof title !== "string") ||
          data.locations.some((location) => typeof location !== "string")
        ) {
          throw new Error(
            "Saved search preferences contain invalid values."
          );
        }

        setSavedSearchPreferences(data);
      } catch (error) {
        if (!controller.signal.aborted) {
          setPreferencesError(
            error.message || "Unable to load saved search preferences."
          );
        }
      } finally {
        if (!controller.signal.aborted) {
          setPreferencesLoading(false);
          setPreferencesChecked(true);
        }
      }
    }

    loadSavedSearchPreferences();

    return () => controller.abort();
  }, [activePage, user]);

  // Helper function to format salary for display.
  const formatSalaryLabel = (val) =>
    new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      maximumFractionDigits: 0,
    }).format(val);

  // JH-021: Saved preferences restrict the displayed results.
  // Local search filters can narrow results but cannot expand
  // the user's saved workplace restrictions.
  const filteredAvailableJobs = jobPostings.filter((job) => {
    const saved = savedSearchPreferences;

    const savedTitles = saved?.job_titles ?? [];
    const savedLocations = saved?.locations ?? [];
    const savedWorkplaceTypes = saved?.workplace_type ?? [];

    const normalizedTitle = job.title.toLowerCase();
    const normalizedLocation = job.location.toLowerCase();
    const normalizedWorkplace = job.workplace_type?.toLowerCase();

    const matchesSavedTitles =
      savedTitles.length === 0 ||
      savedTitles.some((title) =>
        normalizedTitle.includes(title.toLowerCase())
      );

    const matchesSavedLocations =
      savedLocations.length === 0 ||
      savedLocations.some((location) =>
        normalizedLocation.includes(location.toLowerCase())
      );

    const matchesSavedWorkplace =
      savedWorkplaceTypes.length === 0 ||
      savedWorkplaceTypes.includes(normalizedWorkplace);

    const matchesTitle = normalizedTitle.includes(
      jobTitleSearch.toLowerCase()
    );

    const matchesLocation = normalizedLocation.includes(
      jobLocation.toLowerCase()
    );

    const matchesWorkplace =
      workplaceType === "Any type" ||
      normalizedWorkplace === workplaceType.toLowerCase();

    const matchesSalary =
      (job.salary_min == null || job.salary_min <= maxSalary) &&
      (job.salary_max == null || job.salary_max >= minSalary);

    return (
      matchesSavedTitles &&
      matchesSavedLocations &&
      matchesSavedWorkplace &&
      matchesTitle &&
      matchesLocation &&
      matchesWorkplace &&
      matchesSalary
    );
  });

  const statuses = [
    "Applied",
    "In Progress",
    "Interview",
    "Offer",
    "Rejected",
  ];

  const filteredJobs = useMemo(() => {
    return jobs.filter((job) => {
      const term = search.toLowerCase();

      const matchesSearch =
        job.company.toLowerCase().includes(term) ||
        job.position.toLowerCase().includes(term) ||
        job.location.toLowerCase().includes(term);

      const matchesStatus =
        filter === "All Statuses" || job.status === filter;

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
    if (PRIVATE_PAGES.includes(page) && !user) {
      setReturnPage(page);
      setSidebarOpen(false);
      setLoginOpen(true);
      return;
    }

    setActivePage(page);
    setSidebarOpen(false);
    setSelectedJob(null);
  }

  function updateStatus(id, status) {
    setJobs((current) =>
      current.map((job) =>
        job.id === id ? { ...job, status } : job
      )
    );

    setSelectedJob((current) =>
      current?.id === id ? { ...current, status } : current
    );
  }

  function handleTrackJob(job) {
    const alreadyApplied = jobs.some(
      (application) =>
        application.company === job.company &&
        application.position === job.title
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

  // Do not display unrestricted results while a signed-in user's
  // saved preferences are being checked or if the request fails.
  const canShowPostings =
    !user ||
    (!preferencesLoading &&
      preferencesChecked &&
      !preferencesError);

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
        loggedIn={Boolean(user)}
        userEmail={user?.email}
        onToggleLogin={handleAuthAction}
        authLoading={authLoading}
        loggingOut={loggingOut}
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

          <span className="breadcrumb">
            Workspace / {activePage}
          </span>

          <div className="topbar-right">
            <span className="topbar-label">JOB APPLICATIONS</span>

            <div className="avatar small-avatar">
              {user?.email?.[0]?.toUpperCase() || "U"}
            </div>
          </div>
        </header>

        {authMessage && (
          <p className="auth-status" role="status">
            {authMessage}
          </p>
        )}

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

              {user && !canShowPostings && !preferencesError && (
                <p role="status">
                  Loading saved search preferences...
                </p>
              )}

              {user && preferencesError && (
                <p className="profile-form-error" role="alert">
                  {preferencesError} Results are temporarily unavailable
                  because your saved restrictions could not be verified.
                </p>
              )}

              {user && canShowPostings && savedSearchPreferences && (
                <p className="profile-field-hint" role="status">
                  Your saved job search preferences are applied
                  to these results.
                  {savedSearchPreferences.workplace_type.length > 0 && (
                    <>
                      {" "}Allowed workplace types:{" "}
                      {savedSearchPreferences.workplace_type.join(", ")}.
                    </>
                  )}
                </p>
              )}

              <label htmlFor="job-title-search">
                Job title
              </label>

              <div className="posting-search">
                <Search size={19} />

                <input
                  id="job-title-search"
                  placeholder="Search job titles, e.g. Data Analyst"
                  value={jobTitleSearch}
                  onChange={(e) =>
                    setJobTitleSearch(e.target.value)
                  }
                />
              </div>

              <div className="posting-filters">
                <div className="filter-field">
                  <label htmlFor="workplace-filter">
                    Workplace type
                  </label>

                  <select
                    id="workplace-filter"
                    value={workplaceType}
                    onChange={(e) =>
                      setWorkplaceType(e.target.value)
                    }
                  >
                    <option value="Any type">
                      Any type
                    </option>
                    <option value="Remote">
                      Remote
                    </option>
                    <option value="Hybrid">
                      Hybrid
                    </option>
                    <option value="onsite">
                      On-site
                    </option>
                  </select>
                </div>

                <div className="filter-field">
                  <label htmlFor="location-filter">
                    Location
                  </label>

                  <div className="posting-search location-search">
                    <MapPin size={18} />

                    <input
                      id="location-filter"
                      placeholder="City, state, or remote"
                      value={jobLocation}
                      onChange={(e) =>
                        setJobLocation(e.target.value)
                      }
                    />
                  </div>
                </div>

                {/* Min & Max Salary Sliders Side-by-Side */}
                <div className="salary-filters-row">
                  <div className="filter-field slider-filter-field">
                    <label>
                      Min Salary:{" "}
                      <strong>
                        {formatSalaryLabel(minSalary)}
                      </strong>
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

                        if (val > maxSalary) {
                          setMaxSalary(val);
                        }
                      }}
                    />
                  </div>

                  <div className="filter-field slider-filter-field">
                    <label>
                      Max Salary:{" "}
                      <strong>
                        {formatSalaryLabel(maxSalary)}
                      </strong>
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

                        if (val < minSalary) {
                          setMinSalary(val);
                        }
                      }}
                    />
                  </div>
                </div>
              </div>

              <div className="posting-results-header">
                <h2>Matching jobs</h2>

                <span>
                  {canShowPostings
                    ? filteredAvailableJobs.length
                    : 0}{" "}
                  results
                </span>
              </div>

              <div className="posting-results">
                {canShowPostings &&
                  filteredAvailableJobs.map((job) => (
                    <JobPostingCard
                      key={job.job_id}
                      job={job}
                      onTrack={handleTrackJob}
                    />
                  ))}

                {canShowPostings &&
                  filteredAvailableJobs.length === 0 && (
                    <p className="postings-empty">
                      No matching jobs. Try changing your search
                      or filters. Your saved preferences will
                      remain in effect.
                    </p>
                  )}
              </div>
            </section>
          </section>
        ) : activePage === "Dashboard" ||
          activePage === "Applied Jobs" ? (
          <>
            <section className="page-heading">
              <div>
                <p className="eyebrow">
                  YOUR CAREER WORKSPACE
                </p>

                <h1>
                  {activePage === "Dashboard"
                    ? "Dashboard"
                    : "Applied Jobs"}
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

                  <p>
                    Review and update your job search progress.
                  </p>
                </div>

                <span className="results-count">
                  {filteredJobs.length} jobs
                </span>
              </div>

              <div className="table-toolbar">
                <div className="search-box">
                  <Search size={18} />

                  <input
                    aria-label="Search jobs"
                    placeholder="Search company, title or location..."
                    value={search}
                    onChange={(e) =>
                      setSearch(e.target.value)
                    }
                  />
                </div>

                <select
                  aria-label="Filter by status"
                  value={filter}
                  onChange={(e) =>
                    setFilter(e.target.value)
                  }
                >
                  <option>All Statuses</option>

                  {statuses.map((status) => (
                    <option key={status}>
                      {status}
                    </option>
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
                        <td
                          colSpan="5"
                          className="empty-state"
                        >
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

            <p className="eyebrow">
              ACCOUNT SETTINGS
            </p>

            <h1>Profile</h1>

            <p>
              Manage your profile and job search preferences.
            </p>

            {user && (
              <>
                <ProfileForm />
                <SearchPreferencesForm />
              </>
            )}
          </section>
        )}
      </main>

      {selectedJob && (
        <div
          className="modal-backdrop"
          onClick={() =>
            setSelectedJob(null)
          }
        >
          <section
            className="job-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="job-modal-title"
            onClick={(e) =>
              e.stopPropagation()
            }
          >
            <div className="modal-heading">
              <div>
                <p className="eyebrow">
                  APPLICATION DETAILS
                </p>

                <h2 id="job-modal-title">
                  {selectedJob.company}
                </h2>

                <p>
                  {selectedJob.position}
                </p>
              </div>

              <button
                className="icon-button"
                aria-label="Close details"
                onClick={() =>
                  setSelectedJob(null)
                }
              >
                ×
              </button>
            </div>

            <p className="detail-label">
              Location
            </p>

            <p>
              {selectedJob.location}
            </p>

            <p className="detail-label">
              Application status
            </p>

            <select
              value={selectedJob.status}
              onChange={(e) =>
                updateStatus(
                  selectedJob.id,
                  e.target.value
                )
              }
            >
              {statuses.map((status) => (
                <option key={status}>
                  {status}
                </option>
              ))}
            </select>

            <button
              className="primary-button modal-done"
              onClick={() =>
                setSelectedJob(null)
              }
            >
              Done
            </button>
          </section>
        </div>
      )}

      {loginOpen && (
        <LoginForm
          notice={loginNotice}
          onClose={() => {
            setLoginOpen(false);
            setLoginNotice("");
            setReturnPage(null);
          }}
          onLogin={(currentUser) => {
            setUser(currentUser);
            setLoginOpen(false);
            setLoginNotice("");
            setAuthMessage("");
            setActivePage(
              returnPage || DEFAULT_PRIVATE_PAGE
            );
            setReturnPage(null);
            setSelectedJob(null);
          }}
        />
      )}
    </div>
  );
}
