import { useEffect, useRef, useState } from "react";

type Theme = "light" | "dark" | "brown" | "custom";
type Mode = "light" | "dark";
interface Custom {
  hue: number; // 0..360
  tone: number; // 0..1: от почти белого/серого до насыщенного
  mode: Mode;
}

const THEMES: { id: Theme; label: string }[] = [
  { id: "light", label: "Светлая" },
  { id: "dark", label: "Тёмная" },
  { id: "brown", label: "Коричневая" },
  { id: "custom", label: "Своя" },
];
const DEFAULT_CUSTOM: Custom = { hue: 190, tone: 0.6, mode: "dark" };

const systemTheme = (): Theme => (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");

function read(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function write(key: string, value: string) {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* без хранилища тема просто не запомнится */
  }
}

function storedTheme(): Theme | null {
  const v = read("theme");
  return THEMES.some((t) => t.id === v) ? (v as Theme) : null;
}

function storedCustom(): Custom {
  try {
    const c = JSON.parse(read("customTheme") ?? "");
    if (typeof c.hue === "number" && typeof c.tone === "number" && (c.mode === "light" || c.mode === "dark")) return c;
  } catch {
    /* битый JSON — берём по умолчанию */
  }
  return DEFAULT_CUSTOM;
}

function customVars({ hue: h, tone, mode }: Custom): Record<string, string> {
  const s = Math.round(15 + tone * 70);
  const ss = Math.round(s * 0.6);
  const bg = mode === "dark" ? [24, 18, 28, 22] : [40, 32, 44, 36];
  const bgVars = {
    "--bg-a": `hsl(${h} ${s}% ${bg[0]}%)`,
    "--bg-b": `hsl(${h + 25} ${s}% ${bg[1]}%)`,
    "--bg-c": `hsl(${h - 25} ${s}% ${bg[2]}%)`,
    "--bg-d": `hsl(${h + 50} ${s}% ${bg[3]}%)`,
  };
  if (mode === "light") {
    return {
      ...bgVars,
      "--scrim": `hsla(${h} ${s}% 10% / 0.35)`,
      "--glass": `hsla(${h} ${ss}% 97% / 0.5)`,
      "--glass-strong": `hsla(${h} ${ss}% 97% / 0.62)`,
      "--glass-hover": `hsla(${h} ${ss}% 97% / 0.72)`,
      "--col": `hsla(${h} ${ss}% 97% / 0.2)`,
      "--card": `hsla(${h} ${ss}% 97% / 0.55)`,
      "--pill": "rgba(0, 0, 0, 0.08)",
      "--plus-bg": "rgba(0, 0, 0, 0.1)",
      "--plus": `hsl(${h} ${s}% 28%)`,
      "--accent-on-card": `hsl(${h} ${s}% 28%)`,
      "--accent": `hsl(${h} ${s}% 30%)`,
      "--on-accent": "#ffffff",
      "--text": `hsl(${h} 30% 10%)`,
      "--muted": `hsl(${h} 15% 30%)`,
      "--border": "rgba(255, 255, 255, 0.3)",
      "--edge": "rgba(255, 255, 255, 0.45)",
      "--danger": "#b42318",
      "--low": "#6b7280",
      "--high": "#a85a00",
      "--urgent": "#b42318",
    };
  }
  return {
    ...bgVars,
    "--scrim": `hsla(${h} ${s}% 8% / 0.5)`,
    "--glass": `hsla(${h} ${ss}% 14% / 0.72)`,
    "--glass-strong": `hsla(${h} ${ss}% 14% / 0.8)`,
    "--glass-hover": `hsla(${h} ${ss}% 26% / 0.9)`,
    "--col": `hsla(${h} ${ss}% 11% / 0.55)`,
    "--card": `hsla(${h} ${ss}% 22% / 0.75)`,
    "--pill": "rgba(255, 255, 255, 0.14)",
    "--plus-bg": "rgba(255, 255, 255, 0.16)",
    "--plus": `hsl(${h} 90% 78%)`,
    "--accent-on-card": `hsl(${h} 90% 78%)`,
    "--accent": `hsl(${h} 90% 78%)`,
    "--on-accent": "#0b1220",
    "--text": "#f3f4f6",
    "--muted": `hsl(${h} 15% 78%)`,
    "--border": "rgba(255, 255, 255, 0.1)",
    "--edge": "rgba(255, 255, 255, 0.15)",
    "--danger": "#ff9b94",
    "--low": "#aab3c2",
    "--high": "#ffb454",
    "--urgent": "#ff8a80",
  };
}

let applied: string[] = [];

function applyTheme(theme: Theme, custom: Custom) {
  const root = document.documentElement;
  root.dataset.theme = theme;
  for (const k of applied) root.style.removeProperty(k);
  applied = [];
  if (theme !== "custom") return;
  for (const [k, v] of Object.entries(customVars(custom))) {
    root.style.setProperty(k, v);
    applied.push(k);
  }
}

/** Применяет сохранённую тему до первого рендера, чтобы не мигало. */
export function initTheme() {
  const t = storedTheme();
  if (t) applyTheme(t, storedCustom());
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(() => storedTheme() ?? systemTheme());
  const [custom, setCustom] = useState<Custom>(storedCustom);
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (e: PointerEvent) => {
      if (!box.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", close);
    return () => document.removeEventListener("pointerdown", close);
  }, [open]);

  const choose = (t: Theme) => {
    setTheme(t);
    applyTheme(t, custom);
    write("theme", t);
  };

  const change = (patch: Partial<Custom>) => {
    const next = { ...custom, ...patch };
    setCustom(next);
    setTheme("custom");
    applyTheme("custom", next);
    write("theme", "custom");
    write("customTheme", JSON.stringify(next));
  };

  const label = THEMES.find((t) => t.id === theme)!.label;
  const sat = Math.round(15 + custom.tone * 70);

  return (
    <div className="theme-box" ref={box}>
      <button onClick={() => setOpen(!open)} aria-expanded={open} aria-label="Настройка темы">
        🎨 {label}
      </button>
      {open && (
        <div className="theme-panel" role="dialog" aria-label="Настройка темы">
          <div className="seg">
            {THEMES.map((t) => (
              <button key={t.id} className={theme === t.id ? "active" : ""} onClick={() => choose(t.id)}>
                {t.label}
              </button>
            ))}
          </div>
          <div className="theme-custom">
            <label>
              Цвет
              <input
                type="range"
                className="slider hue"
                min={0}
                max={360}
                value={custom.hue}
                style={{ "--thumb": `hsl(${custom.hue} 90% 55%)` } as React.CSSProperties}
                onChange={(e) => change({ hue: Number(e.target.value) })}
              />
            </label>
            <label>
              Насыщенность
              <input
                type="range"
                className="slider tone"
                min={0}
                max={100}
                value={Math.round(custom.tone * 100)}
                style={
                  {
                    "--thumb": `hsl(${custom.hue} ${sat}% 50%)`,
                    "--to": `hsl(${custom.hue} 100% 55%)`,
                  } as React.CSSProperties
                }
                onChange={(e) => change({ tone: Number(e.target.value) / 100 })}
              />
            </label>
            <div className="seg">
              <button className={custom.mode === "light" ? "active" : ""} onClick={() => change({ mode: "light" })}>
                Светлые
              </button>
              <button className={custom.mode === "dark" ? "active" : ""} onClick={() => change({ mode: "dark" })}>
                Тёмные
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
