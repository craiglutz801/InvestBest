type RunWindow = {
  day: number;
  hour: number;
  minute: number;
};

const PACIFIC_TIME_ZONE = "America/Los_Angeles";
const RUN_WINDOW_TOLERANCE_MINUTES = 5;

const MARKET_RUN_WINDOWS: RunWindow[] = [
  { day: 1, hour: 6, minute: 35 },
  { day: 1, hour: 7, minute: 35 },
  { day: 1, hour: 8, minute: 35 },
  { day: 1, hour: 9, minute: 35 },
  { day: 1, hour: 10, minute: 35 },
  { day: 1, hour: 11, minute: 35 },
  { day: 1, hour: 12, minute: 35 },
  { day: 2, hour: 6, minute: 35 },
  { day: 2, hour: 7, minute: 35 },
  { day: 2, hour: 8, minute: 35 },
  { day: 2, hour: 9, minute: 35 },
  { day: 2, hour: 10, minute: 35 },
  { day: 2, hour: 11, minute: 35 },
  { day: 2, hour: 12, minute: 35 },
  { day: 3, hour: 6, minute: 35 },
  { day: 3, hour: 7, minute: 35 },
  { day: 3, hour: 8, minute: 35 },
  { day: 3, hour: 9, minute: 35 },
  { day: 3, hour: 10, minute: 35 },
  { day: 3, hour: 11, minute: 35 },
  { day: 3, hour: 12, minute: 35 },
  { day: 4, hour: 6, minute: 35 },
  { day: 4, hour: 7, minute: 35 },
  { day: 4, hour: 8, minute: 35 },
  { day: 4, hour: 9, minute: 35 },
  { day: 4, hour: 10, minute: 35 },
  { day: 4, hour: 11, minute: 35 },
  { day: 4, hour: 12, minute: 35 },
  { day: 5, hour: 6, minute: 35 },
  { day: 5, hour: 7, minute: 35 },
  { day: 5, hour: 8, minute: 35 },
  { day: 5, hour: 9, minute: 35 },
  { day: 5, hour: 10, minute: 35 },
  { day: 5, hour: 11, minute: 35 },
  { day: 5, hour: 12, minute: 35 },
];

type ZonedDateParts = {
  year: number;
  month: number;
  dayOfMonth: number;
  day: number;
  hour: number;
  minute: number;
};

const zonedDateFormatter = new Intl.DateTimeFormat("en-US", {
  timeZone: PACIFIC_TIME_ZONE,
  weekday: "short",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

const zonedTimestampFormatter = new Intl.DateTimeFormat("en-US", {
  timeZone: PACIFIC_TIME_ZONE,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hourCycle: "h23",
});

const WEEKDAY_TO_INDEX: Record<string, number> = {
  Sun: 0,
  Mon: 1,
  Tue: 2,
  Wed: 3,
  Thu: 4,
  Fri: 5,
  Sat: 6,
};

function getPacificParts(date: Date): ZonedDateParts {
  const partMap = zonedDateFormatter.formatToParts(date).reduce<Record<string, string>>((acc, part) => {
    if (part.type !== "literal") {
      acc[part.type] = part.value;
    }

    return acc;
  }, {});

  return {
    year: Number(partMap.year),
    month: Number(partMap.month),
    dayOfMonth: Number(partMap.day),
    day: WEEKDAY_TO_INDEX[partMap.weekday] ?? date.getDay(),
    hour: Number(partMap.hour),
    minute: Number(partMap.minute),
  };
}

function getTimeZoneOffsetMilliseconds(date: Date): number {
  const partMap = zonedTimestampFormatter.formatToParts(date).reduce<Record<string, string>>((acc, part) => {
    if (part.type !== "literal") {
      acc[part.type] = part.value;
    }

    return acc;
  }, {});

  const asUtcTimestamp = Date.UTC(
    Number(partMap.year),
    Number(partMap.month) - 1,
    Number(partMap.day),
    Number(partMap.hour),
    Number(partMap.minute),
    Number(partMap.second),
  );

  return asUtcTimestamp - date.getTime();
}

function createPacificDate(year: number, month: number, dayOfMonth: number, hour: number, minute: number): Date {
  const utcGuess = new Date(Date.UTC(year, month - 1, dayOfMonth, hour, minute, 0));
  const initialOffset = getTimeZoneOffsetMilliseconds(utcGuess);
  const resolved = new Date(utcGuess.getTime() - initialOffset);
  const resolvedOffset = getTimeZoneOffsetMilliseconds(resolved);

  if (resolvedOffset !== initialOffset) {
    return new Date(utcGuess.getTime() - resolvedOffset);
  }

  return resolved;
}

function getPacificDateWithOffset(base: Date, offsetDays: number): ZonedDateParts {
  const candidate = new Date(base.getTime() + offsetDays * 24 * 60 * 60 * 1000);
  return getPacificParts(candidate);
}

export function isScheduledMarketRunTime(now = new Date()): boolean {
  const { day, hour, minute } = getPacificParts(now);
  return MARKET_RUN_WINDOWS.some(
    (window) =>
      window.day === day &&
      window.hour === hour &&
      minute >= window.minute &&
      minute < window.minute + RUN_WINDOW_TOLERANCE_MINUTES,
  );
}

export function getScheduledSlotKey(now = new Date()): string | null {
  const { year, month, dayOfMonth, day, hour, minute } = getPacificParts(now);
  const matchedWindow = MARKET_RUN_WINDOWS.find(
    (window) =>
      window.day === day &&
      window.hour === hour &&
      minute >= window.minute &&
      minute < window.minute + RUN_WINDOW_TOLERANCE_MINUTES,
  );

  if (!matchedWindow) {
    return null;
  }

  return `${year}-${String(month).padStart(2, "0")}-${String(dayOfMonth).padStart(2, "0")}-${matchedWindow.hour}-${matchedWindow.minute}`;
}

export function getNextScheduledRun(now = new Date()): Date | null {
  for (let offset = 0; offset < 8; offset += 1) {
    const candidateDate = getPacificDateWithOffset(now, offset);
    const windows = MARKET_RUN_WINDOWS
      .filter((window) => window.day === candidateDate.day)
      .sort((left, right) => left.hour - right.hour || left.minute - right.minute);

    for (const window of windows) {
      const scheduled = createPacificDate(
        candidateDate.year,
        candidateDate.month,
        candidateDate.dayOfMonth,
        window.hour,
        window.minute,
      );
      if (scheduled > now) {
        return scheduled;
      }
    }
  }

  return null;
}
