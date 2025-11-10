import { useState } from "react";

export default function Auth({ onAuthenticated }) {
  const [mode, setMode] = useState("login"); // 'login' | 'register'
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const API = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const endpoint = mode === "register" ? "/register" : "/token";
      const body = mode === "register"
        ? { username, email, password }
        : new URLSearchParams({ username, password });

      const response = await fetch(`${API}${endpoint}`, {
        method: "POST",
        headers: mode === "register"
          ? { "Content-Type": "application/json" }
          : { "Content-Type": "application/x-www-form-urlencoded" },
        body: mode === "register" ? JSON.stringify(body) : body,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || errorData.error || "Authentication failed");
      }

      const data = await response.json();
      const token = data.access_token;

      // Store token in localStorage
      localStorage.setItem("auth_token", token);
      localStorage.setItem("username", username);

      // Notify parent component
      onAuthenticated({ token, username });
    } catch (err) {
      setError(err.message || "Authentication failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={styles.container}>
      <div style={styles.card}>
        <h2>{mode === "login" ? "Login" : "Register"}</h2>

        {error && (
          <div style={styles.error}>
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} style={styles.form}>
          <div style={styles.field}>
            <label style={styles.label}>Username</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              minLength={3}
              style={styles.input}
              placeholder="Enter username"
            />
          </div>

          {mode === "register" && (
            <div style={styles.field}>
              <label style={styles.label}>Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                style={styles.input}
                placeholder="Enter email"
              />
            </div>
          )}

          <div style={styles.field}>
            <label style={styles.label}>Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
              style={styles.input}
              placeholder="Enter password"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            style={styles.button}
          >
            {loading ? "Please wait..." : (mode === "login" ? "Login" : "Register")}
          </button>
        </form>

        <div style={styles.toggle}>
          {mode === "login" ? (
            <span>
              Don't have an account?{" "}
              <button
                onClick={() => setMode("register")}
                style={styles.linkButton}
              >
                Register
              </button>
            </span>
          ) : (
            <span>
              Already have an account?{" "}
              <button
                onClick={() => setMode("login")}
                style={styles.linkButton}
              >
                Login
              </button>
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

const styles = {
  container: {
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
    minHeight: "100vh",
    backgroundColor: "#f5f5f5",
  },
  card: {
    backgroundColor: "white",
    padding: "40px",
    borderRadius: "8px",
    boxShadow: "0 2px 10px rgba(0,0,0,0.1)",
    width: "100%",
    maxWidth: "400px",
  },
  form: {
    marginTop: "20px",
  },
  field: {
    marginBottom: "15px",
  },
  label: {
    display: "block",
    marginBottom: "5px",
    fontWeight: "bold",
    fontSize: "14px",
  },
  input: {
    width: "100%",
    padding: "10px",
    border: "1px solid #ddd",
    borderRadius: "4px",
    fontSize: "14px",
    boxSizing: "border-box",
  },
  button: {
    width: "100%",
    padding: "12px",
    backgroundColor: "#0066cc",
    color: "white",
    border: "none",
    borderRadius: "4px",
    fontSize: "16px",
    fontWeight: "bold",
    cursor: "pointer",
    marginTop: "10px",
  },
  error: {
    padding: "10px",
    backgroundColor: "#fee",
    border: "1px solid #fcc",
    borderRadius: "4px",
    color: "#c00",
    marginBottom: "15px",
  },
  toggle: {
    marginTop: "20px",
    textAlign: "center",
    fontSize: "14px",
  },
  linkButton: {
    background: "none",
    border: "none",
    color: "#0066cc",
    cursor: "pointer",
    textDecoration: "underline",
    padding: 0,
    font: "inherit",
  },
};
