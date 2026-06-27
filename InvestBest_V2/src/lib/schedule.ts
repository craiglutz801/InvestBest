type RunWindow = {
  day: number;
  hour: number;
  minute: number;
};

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

function cloneAtLocalTime(base: Date, hour: number, minute: number): Date {
  const next = new Date(base);
  next.setHours(hour, minute, 0, 0);
  return next;
}

export function isScheduledMarketRunTime(now = new Date()): boolean {
  const day = now.getDay();
  const hour = now.getHours();
  const minute = now.getMinutes();
  return MARKET_RUN_WINDOWS.some(
    (window) =>
      window.day === day &&
      window.hour === hour &&
      minute >= window.minute &&
      minute < window.minute + RUN_WINDOW_TOLERANCE_MINUTES,
  );
}

export function getScheduledSlotKey(now = new Date()): string | null {
  const day = now.getDay();
  const hour = now.getHours();
  const minute = now.getMinutes();
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

  const year = now.getFullYear();
  const month = `${now.getMonth() + 1}`.padStart(2, "0");
  const date = `${now.getDate()}`.padStart(2, "0");
  return `${year}-${month}-${date}-${matchedWindow.hour}-${matchedWindow.minute}`;
}

export function getNextScheduledRun(now = new Date()): Date | null {
  for (let offset = 0; offset < 8; offset += 1) {
    const candidateDate = new Date(now);
    candidateDate.setDate(now.getDate() + offset);
    const day = candidateDate.getDay();
    const windows = MARKET_RUN_WINDOWS
      .filter((window) => window.day === day)
      .sort((left, right) => left.hour - right.hour || left.minute - right.minute);

    for (const window of windows) {
      const scheduled = cloneAtLocalTime(candidateDate, window.hour, window.minute);
      if (scheduled > now) {
        return scheduled;
      }
    }
  }

  return null;
}
