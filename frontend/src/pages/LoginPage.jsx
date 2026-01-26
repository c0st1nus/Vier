import React, { useState } from "react";
import { useNavigate, useLocation, Link } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext.jsx";
import "./LoginPage.css";

const LoginPage = () => {
  const { login, register, loading, error } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [mode, setMode] = useState("login"); // "login" | "register"
  const [form, setForm] = useState({ email: "", password: "", confirm: "" });
  const [message, setMessage] = useState("");

  const from = location.state?.from || "/";

  const handleChange = (e) => {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
    setMessage("");
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setMessage("");
    if (mode === "register" && form.password !== form.confirm) {
      setMessage("Пароли не совпадают");
      return;
    }
    try {
      if (mode === "login") {
        await login(form.email.trim(), form.password);
        setMessage("Успешный вход");
      } else {
        await register(form.email.trim(), form.password);
        setMessage("Регистрация завершена");
      }
      navigate(from, { replace: true });
    } catch (err) {
      setMessage(err?.message || "Ошибка авторизации");
    }
  };

  const toggleMode = () => {
    setMode((prev) => (prev === "login" ? "register" : "login"));
    setMessage("");
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <h1 className="auth-title">
          {mode === "login" ? "Вход" : "Регистрация"}
        </h1>
        <p className="auth-subtitle">
          {mode === "login"
            ? "Войдите, чтобы просматривать историю и сохранять прогресс."
            : "Создайте аккаунт, чтобы сохранять историю и результаты."}
        </p>

        <form className="auth-form" onSubmit={handleSubmit}>
          <label className="auth-label" htmlFor="email">
            Email
          </label>
          <input
            className="auth-input"
            id="email"
            name="email"
            type="email"
            placeholder="you@example.com"
            value={form.email}
            onChange={handleChange}
            required
            autoComplete="email"
          />

          <label className="auth-label" htmlFor="password">
            Пароль
          </label>
          <input
            className="auth-input"
            id="password"
            name="password"
            type="password"
            placeholder="••••••••"
            value={form.password}
            onChange={handleChange}
            required
            autoComplete={
              mode === "login" ? "current-password" : "new-password"
            }
            minLength={6}
          />

          {mode === "register" && (
            <>
              <label className="auth-label" htmlFor="confirm">
                Подтверждение пароля
              </label>
              <input
                className="auth-input"
                id="confirm"
                name="confirm"
                type="password"
                placeholder="••••••••"
                value={form.confirm}
                onChange={handleChange}
                required
                minLength={6}
                autoComplete="new-password"
              />
            </>
          )}

          {(message || error) && (
            <div className="auth-message">{message || error}</div>
          )}

          <button className="auth-button" type="submit" disabled={loading}>
            {loading
              ? "Загрузка..."
              : mode === "login"
                ? "Войти"
                : "Зарегистрироваться"}
          </button>
        </form>

        <div className="auth-switch">
          {mode === "login" ? (
            <>
              Нет аккаунта?{" "}
              <button type="button" onClick={toggleMode} className="auth-link">
                Зарегистрироваться
              </button>
            </>
          ) : (
            <>
              Уже есть аккаунт?{" "}
              <button type="button" onClick={toggleMode} className="auth-link">
                Войти
              </button>
            </>
          )}
        </div>

        <div className="auth-back">
          <Link to="/" className="auth-link">
            ← Вернуться на главную
          </Link>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
