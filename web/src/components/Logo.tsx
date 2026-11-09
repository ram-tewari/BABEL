import { Link } from "react-router";

export function Logo() {
  return (
    <Link to="/" className="flex items-center gap-2.5" aria-label="BABEL library">
      <svg width="28" height="28" viewBox="0 0 32 32" aria-hidden>
        <rect width="32" height="32" rx="7" fill="var(--raised)" />
        <path
          d="M9 25h14M11 25V19h10v6M12.5 19v-5h7v5M14 14v-4h4v4M15.2 10V7h1.6v3"
          stroke="var(--accent)"
          strokeWidth="1.8"
          fill="none"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      <span className="font-serif text-lg font-semibold tracking-[0.18em]">BABEL</span>
    </Link>
  );
}
