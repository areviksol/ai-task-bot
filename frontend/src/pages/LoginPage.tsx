
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { exchangeLoginToken } from "../features/auth/auth.api";

export default function LoginPage() {
  const navigate = useNavigate();
  const attempted = useRef(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (attempted.current) return;
    attempted.current = true;

    const fragment = window.location.hash.slice(1);
    const token = new URLSearchParams(fragment).get("token");

    // Remove the sensitive token from the browser URL.
    window.history.replaceState(
      null,
      "",
      window.location.pathname,
    );

    if (!token) {
      setLoading(false);
      setError("Open Telegram and send /login to the bot.");
      return;
    }

    console.log("Login page mounted");
    console.log("Token present:", Boolean(token));
    exchangeLoginToken(token)
      .then(() => navigate("/dashboard", { replace: true }))
      .catch(() => {
        setError("Login link is invalid, expired or already used.");
        setLoading(false);
      });
  }, [navigate]);

  return (
    <main className="auth-page">
      <div className="auth-card">
        <div className="brand-icon">✓</div>
        <h1>AI Task Manager</h1>
        <p>Manage tasks from Telegram and your dashboard.</p>

        {loading ? (
          <p>Signing you in...</p>
        ) : (
          <>
            <p className="error">{error}</p>
            <a
              href="https://t.me/omni_channel_task_management_bot"
              target="_blank"
              rel="noopener noreferrer"
              className="primary-link"
            >
              Open Telegram Bot
            </a>
          </>
        )}
      </div>
    </main>
  );
}
