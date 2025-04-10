import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import jwt_decode from "jwt-decode";

const API_BASE_URL = "http://192.168.213.152:5000/api";

const Login = ({ setRole }) => {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [isForgotPassword, setIsForgotPassword] = useState(false);
  const [email, setEmail] = useState("");
  const [resetToken, setResetToken] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [isResetPassword, setIsResetPassword] = useState(false);
  const navigate = useNavigate();

  // Handle Login
  const handleLogin = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    const trimmedUsername = username.trim();
    const trimmedPassword = password.trim();
    if (!trimmedUsername || !trimmedPassword) {
      setError("Username and password cannot be empty.");
      setLoading(false);
      return;
    }

    try {
      const response = await axios.post(
        `${API_BASE_URL}/login`,
        { username: trimmedUsername, password: trimmedPassword },
        {
          headers: { "Content-Type": "application/json" },
          withCredentials: true,
        }
      );

      console.log("Server Response:", response.data);

      const token = response.data.token; // Ensure the token is correctly extracted
      if (!token) {
        throw new Error("No token received from server.");
      }

      localStorage.setItem("access_token", token);
      const decoded = jwt_decode(token);
      setRole(decoded.role);
      const redirectPath = decoded.role === "admin" ? "/admin-dashboard" : "/user-dashboard";
      navigate(redirectPath, { replace: true });
    } catch (err) {
      console.error("Login error:", err);
      setError(err.response?.data?.error || "Login failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  // Handle Forgot Password
  const handleForgotPassword = async () => {
    setError(null);
    setLoading(true);

    if (!email || !email.includes("@")) {
      setError("Please enter a valid email address.");
      setLoading(false);
      return;
    }

    try {
      const response = await axios.post(
        `${API_BASE_URL}/forgot-password`,
        { email },
        {
          headers: { "Content-Type": "application/json" },
        }
      );

      console.log("Forgot Password Response:", response.data);
      setError("Password reset email sent. Check your inbox.");
      setIsForgotPassword(false);
    } catch (err) {
      const errorDetails = {
        status: err.response?.status,
        message: err.response?.data?.error || err.message,
      };
      console.error("Forgot Password Error:", errorDetails);
      setError(errorDetails.message || "Failed to send password reset email.");
    } finally {
      setLoading(false);
    }
  };

  // Handle Reset Password
  const handleResetPassword = async () => {
    setError(null);
    setLoading(true);

    if (!resetToken || !newPassword || newPassword.length < 6) {
      setError("Reset token and new password (min 6 characters) are required.");
      setLoading(false);
      return;
    }

    try {
      const response = await axios.post(
        `${API_BASE_URL}/reset-password`,
        { token: resetToken, new_password: newPassword },
        {
          headers: { "Content-Type": "application/json" },
        }
      );

      console.log("Reset Password Response:", response.data);
      setError("Password reset successfully. Please login with your new password.");
      setIsResetPassword(false);
    } catch (err) {
      const errorDetails = {
        status: err.response?.status,
        message: err.response?.data?.error || err.message,
      };
      console.error("Reset Password Error:", errorDetails);
      setError(errorDetails.message || "Failed to reset password.");
    } finally {
      setLoading(false);
    }
  };

  // Navigate to Register
  const handleRegisterRedirect = () => {
    navigate("/register");
  };

  return (
    <div style={styles.container}>
      <h1 style={styles.header}>Login</h1>
      {!isForgotPassword && !isResetPassword ? (
        <form onSubmit={handleLogin}>
          <div style={styles.inputGroup}>
            <label style={styles.label}>Username:</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              style={styles.input}
              placeholder="Enter your username"
              disabled={loading}
              autoComplete="username"
            />
          </div>
          <div style={styles.inputGroup}>
            <label style={styles.label}>Password:</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              style={styles.input}
              placeholder="Enter your password"
              disabled={loading}
              autoComplete="current-password"
            />
          </div>
          {error && <p style={styles.errorText}>{error}</p>}
          <button
            type="submit"
            disabled={loading}
            style={{ ...styles.loginButton, ...(loading ? styles.disabledButton : {}) }}
          >
            {loading ? "Logging in..." : "Login"}
          </button>
          <button
            type="button"
            onClick={handleRegisterRedirect}
            disabled={loading}
            style={{ ...styles.registerButton, ...(loading ? styles.disabledButton : {}) }}
          >
            Register
          </button>
          <button
            type="button"
            onClick={() => setIsForgotPassword(true)}
            disabled={loading}
            style={{ ...styles.forgotPasswordButton, ...(loading ? styles.disabledButton : {}) }}
          >
            Forgot Password?
          </button>
        </form>
      ) : isForgotPassword ? (
        <div>
          <h2 style={styles.subHeader}>Forgot Password</h2>
          <div style={styles.inputGroup}>
            <label style={styles.label}>Email:</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              style={styles.input}
              placeholder="Enter your email"
              disabled={loading}
            />
          </div>
          {error && <p style={styles.errorText}>{error}</p>}
          <button
            onClick={handleForgotPassword}
            disabled={loading}
            style={{ ...styles.resetButton, ...(loading ? styles.disabledButton : {}) }}
          >
            {loading ? "Sending email..." : "Send Reset Link"}
          </button>
          <button
            type="button"
            onClick={() => setIsForgotPassword(false)}
            disabled={loading}
            style={{ ...styles.cancelButton, ...(loading ? styles.disabledButton : {}) }}
          >
            Cancel
          </button>
        </div>
      ) : (
        <div>
          <h2 style={styles.subHeader}>Reset Password</h2>
          <div style={styles.inputGroup}>
            <label style={styles.label}>Reset Token:</label>
            <input
              type="text"
              value={resetToken}
              onChange={(e) => setResetToken(e.target.value)}
              required
              style={styles.input}
              placeholder="Enter reset token"
              disabled={loading}
            />
          </div>
          <div style={styles.inputGroup}>
            <label style={styles.label}>New Password:</label>
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
              style={styles.input}
              placeholder="Enter new password"
              disabled={loading}
            />
          </div>
          {error && <p style={styles.errorText}>{error}</p>}
          <button
            onClick={handleResetPassword}
            disabled={loading}
            style={{ ...styles.resetButton, ...(loading ? styles.disabledButton : {}) }}
          >
            {loading ? "Resetting password..." : "Reset Password"}
          </button>
          <button
            type="button"
            onClick={() => setIsResetPassword(false)}
            disabled={loading}
            style={{ ...styles.cancelButton, ...(loading ? styles.disabledButton : {}) }}
          >
            Cancel
          </button>
        </div>
      )}
    </div>
  );
};

// Styling with Mobile Optimization
const styles = {
  container: {
    maxWidth: "90%",
    width: "400px",
    margin: "50px auto",
    padding: "20px",
    border: "1px solid #ddd",
    borderRadius: "8px",
    textAlign: "center",
    backgroundColor: "#f8f9fa",
    boxShadow: "0px 4px 6px rgba(0, 0, 0, 0.1)",
  },
  header: {
    fontSize: "clamp(1.5rem, 5vw, 2rem)",
    marginBottom: "20px",
  },
  subHeader: {
    fontSize: "clamp(1rem, 4vw, 1.5rem)",
    margin: "20px 0 10px",
  },
  inputGroup: {
    marginBottom: "15px",
    textAlign: "left",
  },
  label: {
    fontSize: "16px",
    fontWeight: "bold",
  },
  input: {
    width: "100%",
    padding: "10px",
    marginTop: "5px",
    borderRadius: "5px",
    border: "1px solid #ccc",
    fontSize: "16px",
    boxSizing: "border-box",
  },
  errorText: {
    color: "red",
    fontSize: "14px",
    margin: "10px 0",
  },
  loginButton: {
    width: "100%",
    padding: "12px",
    backgroundColor: "#007BFF",
    color: "#fff",
    border: "none",
    borderRadius: "5px",
    cursor: "pointer",
    fontSize: "16px",
    marginBottom: "10px",
  },
  registerButton: {
    width: "100%",
    padding: "12px",
    backgroundColor: "#28A745",
    color: "#fff",
    border: "none",
    borderRadius: "5px",
    cursor: "pointer",
    fontSize: "16px",
    marginBottom: "10px",
  },
  forgotPasswordButton: {
    width: "100%",
    padding: "12px",
    backgroundColor: "#6C757D",
    color: "#fff",
    border: "none",
    borderRadius: "5px",
    cursor: "pointer",
    fontSize: "16px",
    marginBottom: "10px",
  },
  resetButton: {
    width: "100%",
    padding: "12px",
    backgroundColor: "#007BFF",
    color: "#fff",
    border: "none",
    borderRadius: "5px",
    cursor: "pointer",
    fontSize: "16px",
    marginBottom: "10px",
  },
  cancelButton: {
    width: "100%",
    padding: "12px",
    backgroundColor: "#6C757D",
    color: "#fff",
    border: "none",
    borderRadius: "5px",
    cursor: "pointer",
    fontSize: "16px",
  },
  disabledButton: {
    opacity: 0.6,
    cursor: "not-allowed",
  },
};

export default Login;