const FLAGS: Record<string, string> = {
  australia: "🇦🇺",
  bahrain: "🇧🇭",
  "saudi arabia": "🇸🇦",
  japan: "🇯🇵",
  china: "🇨🇳",
  "united states": "🇺🇸",
  usa: "🇺🇸",
  miami: "🇺🇸",
  italy: "🇮🇹",
  "emilia romagna": "🇮🇹",
  monaco: "🇲🇨",
  spain: "🇪🇸",
  canada: "🇨🇦",
  austria: "🇦🇹",
  "united kingdom": "🇬🇧",
  "great britain": "🇬🇧",
  britain: "🇬🇧",
  belgium: "🇧🇪",
  hungary: "🇭🇺",
  netherlands: "🇳🇱",
  azerbaijan: "🇦🇿",
  singapore: "🇸🇬",
  mexico: "🇲🇽",
  "mexico city": "🇲🇽",
  brazil: "🇧🇷",
  "sao paulo": "🇧🇷",
  qatar: "🇶🇦",
  uae: "🇦🇪",
  "abu dhabi": "🇦🇪",
  "las vegas": "🇺🇸",
  malaysia: "🇲🇾",
  sepang: "🇲🇾",
  madrid: "🇪🇸",
  madring: "🇪🇸",
};

export function countryFlag(country?: string | null, circuitKey?: string | null): string {
  for (const raw of [country, circuitKey]) {
    if (!raw) continue;
    const key = raw.trim().toLowerCase().replace(/[_-]/g, " ");
    if (FLAGS[key]) return FLAGS[key];
    for (const [needle, flag] of Object.entries(FLAGS)) {
      if (key.includes(needle) || needle.includes(key)) return flag;
    }
  }
  return "🏁";
}
