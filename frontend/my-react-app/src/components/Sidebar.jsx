import { BriefcaseBusiness, LogIn, LogOut, ChevronRight, LayoutDashboard, FileText, Briefcase } from "lucide-react";

const navItems = [
  { label: "Job Postings", icon: Briefcase },
  { label: "Dashboard", icon: LayoutDashboard },
  { label: "Applied Jobs", icon: FileText },
];

export default function Sidebar({
  activePage,
  onNavigate,
  loggedIn,
  userEmail,
  onToggleLogin,
  authLoading,
  loggingOut,
  sidebarOpen,
}) {
  return (
    <aside className={`sidebar ${sidebarOpen ? "sidebar-open" : ""}`}>
      <div className="brand">
        <span className="brand-icon">
          <BriefcaseBusiness size={23} />
        </span>
        <span>JobHunt</span>
      </div>

      <nav className="main-nav" aria-label="Main navigation">
        <p className="nav-heading">WORKSPACE</p>
        {navItems.map(({ label, icon: Icon }) => (
          <button
            key={label}
            className={`nav-item ${activePage === label ? "active" : ""}`}
            onClick={() => onNavigate(label)}
          >
            <Icon size={19} />
            <span>{label}</span>
          </button>
        ))}
      </nav>

      <div className="sidebar-divider" />

      <section className="profile-section">
        <p className="nav-heading">ACCOUNT</p>
        <button
          className={`user-card user-card-button ${
            activePage === "Profile" ? "user-card-active" : ""
          }`}
          onClick={() => onNavigate("Profile")}
        >
          <div className="avatar">{userEmail?.[0]?.toUpperCase() || "U"}</div>
          <div className="user-info">
            <strong>{userEmail || "Your Profile"}</strong>
            <span>{loggedIn ? "View profile & preferences" : "Sign in to manage your profile"}</span>
          </div>
          <ChevronRight size={17} className="profile-chevron" />
        </button>
      </section>

      <div className="sidebar-bottom">
        <div className="sidebar-divider" />
        <button className="nav-item login-item" onClick={onToggleLogin} disabled={authLoading || loggingOut}>
          {loggedIn ? <LogOut size={19} /> : <LogIn size={19} />}
          <span>{authLoading ? "Checking session..." : loggingOut ? "Logging out..." : loggedIn ? "Log Out" : "Log In"}</span>
        </button>
      </div>
    </aside>
  );
}
