import { useState } from "react";

function messageFrom(data, fallback) {
  return data?.error?.message || data?.detail || fallback;
}

export default function LoginForm({ onLogin, onClose, notice }) {
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setError("");
    setMessage("");
    setSubmitting(true);

    try {
      const registering = mode === "register";
      const response = await fetch(`/api/auth/${registering ? "register" : "login"}`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim(), password }),
      });
      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        const fallback = registering
          ? "Unable to create your account. Check your details and try again."
          : "Unable to sign in. Please try again.";
        throw new Error(messageFrom(data, fallback));
      }

      if (registering) {
        setMode("login");
        setPassword("");
        setMessage("Account created. Sign in with your new account to continue.");
      } else {
        onLogin(data.user);
      }
    } catch (err) {
      setError(err instanceof TypeError
        ? "Cannot connect to the server. Check your connection and try again."
        : err.message || "Unable to sign in. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="modal-backdrop auth-backdrop" onMouseDown={(event) => {
      if (event.target === event.currentTarget) onClose();
    }}>
      <section className="auth-card" role="dialog" aria-modal="true" aria-labelledby="login-title">
        <button className="icon-button auth-close" aria-label="Close sign in" onClick={onClose}>×</button>
        {notice && <p className="auth-status auth-notice" role="status">{notice}</p>}
        <p className="eyebrow">{mode === "login" ? "WELCOME BACK" : "GET STARTED"}</p>
        <h1 id="login-title">{mode === "login" ? "Sign in to JobHunt" : "Create your account"}</h1>
        <p className="auth-description">
          {mode === "login" ? "Use your registered email and password to continue." : "Create an account to save your job search progress."}
        </p>
        <form onSubmit={submit}>
          <div className="profile-form-field">
            <label htmlFor="login-email">Email</label>
            <input id="login-email" type="email" autoComplete="email" required maxLength={255}
              value={email} onChange={(event) => setEmail(event.target.value)} />
          </div>
          <div className="profile-form-field">
            <label htmlFor="login-password">Password</label>
            <input id="login-password" type="password" autoComplete={mode === "login" ? "current-password" : "new-password"}
              minLength={mode === "register" ? 8 : 1} required maxLength={128}
              value={password} onChange={(event) => setPassword(event.target.value)} />
            {mode === "register" && <p className="profile-field-hint">Use at least 8 characters.</p>}
          </div>
          {error && <p className="profile-form-error" role="alert">{error}</p>}
          {message && <p className="profile-form-success" role="status">{message}</p>}
          <button className="primary-button auth-submit" type="submit" disabled={submitting}>
            {submitting ? (mode === "login" ? "Signing in..." : "Creating account...") : mode === "login" ? "Sign in" : "Create account"}
          </button>
        </form>
        <p className="auth-switch">
          {mode === "login" ? "New to JobHunt?" : "Already have an account?"}{" "}
          <button type="button" disabled={submitting} onClick={() => {
            setMode(mode === "login" ? "register" : "login");
            setError("");
            setMessage("");
          }}>
            {mode === "login" ? "Create an account" : "Sign in"}
          </button>
        </p>
      </section>
    </div>
  );
}
