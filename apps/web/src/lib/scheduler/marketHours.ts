/**
 * Coarse US-equity market-hours / market-day helper.
 *
 * Strategy Upgrade §2.3, §17 — used by the scheduler tick to optionally skip runs
 * outside market hours / on weekends. Intentionally simple in Sprint 1 (no real
 * NYSE holiday calendar yet); we hold to a conservative 9:30am-4:00pm ET window
 * Mon-Fri, with a small premarket / postmarket grace band that the spec hints at
 * via the "daily before open" / "daily after close" presets.
 *
 * Holidays are out of scope for Sprint 1 — `runOnMarketDaysOnly` only filters
 * weekends. A future regime-engine sprint can swap in a real calendar.
 */

const NY_TZ = "America/New_York";

type EtParts = { weekday: string; hour: number; minute: number };

function nyParts(at: Date): EtParts {
  const fmt = new Intl.DateTimeFormat("en-US", {
    timeZone: NY_TZ,
    weekday: "short",
    hour: "numeric",
    minute: "numeric",
    hour12: false,
  });
  const parts = fmt.formatToParts(at);
  const get = (t: string) => parts.find((p) => p.type === t)?.value ?? "";
  return {
    weekday: get("weekday"),
    hour: Number(get("hour")) || 0,
    minute: Number(get("minute")) || 0,
  };
}

/** True for Mon–Fri ET. Holidays (e.g. Thanksgiving) are NOT yet excluded. */
export function isMarketDayET(at: Date = new Date()): boolean {
  const wd = nyParts(at).weekday;
  return wd !== "Sat" && wd !== "Sun";
}

/**
 * 09:30 ≤ ET time ≤ 16:00 (regular session). When `includeExtended` is true the
 * window opens at 04:00 and closes at 20:00 to roughly match US extended hours.
 */
export function isWithinMarketHoursET(
  at: Date = new Date(),
  options?: { includeExtended?: boolean },
): boolean {
  const { weekday, hour, minute } = nyParts(at);
  if (weekday === "Sat" || weekday === "Sun") return false;

  const minuteOfDay = hour * 60 + minute;
  if (options?.includeExtended) {
    return minuteOfDay >= 4 * 60 && minuteOfDay <= 20 * 60;
  }
  return minuteOfDay >= 9 * 60 + 30 && minuteOfDay <= 16 * 60;
}

export function describeMarketWindow(at: Date = new Date()): string {
  const { weekday, hour, minute } = nyParts(at);
  const hh = String(hour).padStart(2, "0");
  const mm = String(minute).padStart(2, "0");
  if (weekday === "Sat" || weekday === "Sun") return `${weekday} ${hh}:${mm} ET — weekend (closed)`;
  if (isWithinMarketHoursET(at)) return `${weekday} ${hh}:${mm} ET — regular session`;
  return `${weekday} ${hh}:${mm} ET — outside regular session`;
}
