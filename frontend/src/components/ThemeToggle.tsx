import { useState } from "react";

type Theme = "light" | "dark" | "brown";

const systemTheme = (): Theme => (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");

function stored(): Theme | null {
  try {
    const v = localStorage.getItem("theme");
    return v === "light" || v === "dark" || v === "brown" ? v : null;
  } catch {
    return null;
  }
}

/** Применяет сохранённую тему до первого рендера, чтобы не мигало. */
export function initTheme() {
  const t = stored();
  if (t) document.documentElement.dataset.theme = t;
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(() => stored() ?? systemTheme());

  const toggle = () => {
    const next: Theme = theme === "light" ? "dark" : theme === "dark" ? "brown" : "light";
    setTheme(next);
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem("theme", next);
    } catch {
      /* без хранилища тема просто не запомнится */
    }
  };

  const label = { light: "☀️ Светлая", dark: "🌙 Тёмная", brown: "🟤 Коричневая" }[theme];
  return (
    <button onClick={toggle} title="Сменить тему" aria-label="Сменить тему">
      {label}
    </button>
  );
}
