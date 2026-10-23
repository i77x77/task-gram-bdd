import { useEffect, useState, type ReactNode } from "react";
import { api, setPassword } from "../api/client";
import { Logo } from "./Logo";

type State = "checking" | "locked" | "ok";

/** Пускает в приложение, только если сохранённый пароль подходит (или бэкенд работает без пароля). */
export function AuthGate({ children }: { children: ReactNode }) {
  const [state, setState] = useState<State>("checking");
  const [value, setValue] = useState("");
  const [wrong, setWrong] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const lock = () => setState("locked");
    window.addEventListener("auth-required", lock);
    api.checkAuth().then(
      () => setState("ok"),
      () => setState((s) => (s === "checking" ? "locked" : s)), // сеть недоступна — тоже просим ввести пароль
    );
    return () => window.removeEventListener("auth-required", lock);
  }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setWrong(false);
    setPassword(value);
    try {
      await api.checkAuth();
      setState("ok");
      setValue("");
    } catch {
      setPassword("");
      setWrong(true);
    } finally {
      setBusy(false);
    }
  };

  if (state === "ok") return <>{children}</>;
  if (state === "checking") return <div className="empty">Загрузка…</div>;
  return (
    <div className="login">
      <form className="login-card" onSubmit={submit}>
        <Logo />
        <input
          type="password"
          autoFocus
          autoComplete="current-password"
          placeholder="Пароль"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          aria-invalid={wrong}
        />
        {wrong && <div className="login-error">Неверный пароль</div>}
        <button className="primary" type="submit" disabled={busy || !value}>
          Войти
        </button>
      </form>
    </div>
  );
}
