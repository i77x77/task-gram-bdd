/** Логотип Pulse: три скруглённые полосы + слово. Цвет берётся из currentColor. */
export function Logo() {
  return (
    <h1 className="brand">
      <svg className="brand-mark" viewBox="0 0 205 205" aria-hidden="true" fill="currentColor">
        <rect x="7" y="2" width="193" height="56" rx="28" />
        <rect x="22" y="75" width="160" height="56" rx="28" />
        <rect x="3" y="147" width="99" height="56" rx="28" />
      </svg>
      <span className="brand-name">PULSE</span>
    </h1>
  );
}
