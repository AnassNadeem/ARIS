/** Production header destinations. `/test-replay` must never appear here. */
export const NAV_LINKS = [
  { href: "/", label: "Home" },
  { href: "/live", label: "Live" },
  { href: "/replay", label: "Replay" },
  { href: "/standings", label: "Standings" },
] as const;
