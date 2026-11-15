import { useEffect, useState } from "react";
import ChatScreen from "./components/ChatScreen";
import LoginScreen from "./components/LoginScreen";
import TeacherAdminScreen from "./components/TeacherAdminScreen";
import { fetchMe } from "./api";
import "./styles/product-tokens.css";
import "./styles/chat.css";

// NEW 14 Nov 2026 (ADR-017, student login). sessionStorage (not
// localStorage): survives a page refresh within the same tab, cleared
// on tab close. Documented simplification in the ADR -- a proper
// httpOnly refresh-token cookie flow is the hardened version, deferred
// for this single-school pilot.
const TOKEN_STORAGE_KEY = "thutora_token";

function App() {
  const [auth, setAuth] = useState(null); // { token, learner, school } | null
  // "checking" avoids flashing the login screen for a split second
  // while a stored token is still being validated against GET /auth/me
  // on first load.
  const [status, setStatus] = useState("checking");

  useEffect(() => {
    const storedToken = sessionStorage.getItem(TOKEN_STORAGE_KEY);
    if (!storedToken) {
      setStatus("loggedOut");
      return;
    }
    (async () => {
      try {
        const me = await fetchMe(storedToken);
        // NEW 15 Nov 2026 (ADR-024): `role` tells us whether to render
        // ChatScreen or TeacherAdminScreen below -- `me.learner` is now
        // `null` for a teacher, so nothing downstream can accidentally
        // treat a teacher session as a student one just because the
        // field exists.
        setAuth({ token: storedToken, role: me.role, learner: me.learner, school: me.school });
        setStatus("loggedIn");
      } catch {
        sessionStorage.removeItem(TOKEN_STORAGE_KEY);
        setStatus("loggedOut");
      }
    })();
  }, []);

  const handleLogin = (response) => {
    sessionStorage.setItem(TOKEN_STORAGE_KEY, response.access_token);
    setAuth({
      token: response.access_token,
      role: response.role,
      learner: response.learner,
      school: response.school,
    });
    setStatus("loggedIn");
  };

  const handleLogout = () => {
    sessionStorage.removeItem(TOKEN_STORAGE_KEY);
    setAuth(null);
    setStatus("loggedOut");
  };

  if (status === "checking") {
    return <div className="app-loading">Loading…</div>;
  }

  if (status === "loggedOut" || !auth) {
    return <LoginScreen onLogin={handleLogin} />;
  }

  // NEW 15 Nov 2026 (ADR-024): role-aware rendering -- a teacher never
  // sees the student ChatScreen, and vice versa. Same login screen for
  // both (school + login identifier + password); the backend's `role`
  // on the login/me response is what branches here.
  if (auth.role === "teacher") {
    return <TeacherAdminScreen auth={auth} onLogout={handleLogout} />;
  }

  return <ChatScreen auth={auth} onLogout={handleLogout} />;
}

export default App;
