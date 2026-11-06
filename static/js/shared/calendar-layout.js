// Date-only UTC arithmetic keeps month layout independent of browser timezone and DST.
const dayMs = 86400000;
const dayNumber = value => {
  const [year, month, day] = value.slice(0, 10).split('-').map(Number);
  return Date.UTC(year, month - 1, day) / dayMs;
};
const dateKey = day => new Date(day * dayMs).toISOString().slice(0, 10);

export function calendarWeeks(month, schedules) {
  const [year, monthNumber] = month.split('-').map(Number);
  const first = Date.UTC(year, monthNumber - 1, 1) / dayMs;
  const last = Date.UTC(year, monthNumber, 0) / dayMs;
  const gridStart = first - new Date(first * dayMs).getUTCDay();
  const count = Math.ceil((last - gridStart + 1) / 7);
  const events = schedules.filter(s => s.end_at > s.start_at).map(schedule => ({
    schedule,
    start: dayNumber(schedule.start_at),
    // Midnight is exclusive: an event ending at Tuesday 00:00 belongs through Monday.
    end: dayNumber(schedule.end_at) - (/^00:00(?::00(?:\.0+)?)?$/.test(schedule.end_at.slice(11)) ? 1 : 0),
  }));
  const previousLanes = new Map();
  return Array.from({ length: count }, (_, index) => {
    const weekStart = gridStart + index * 7;
    const visibleStart = Math.max(first, weekStart);
    const visibleEnd = Math.min(last, weekStart + 6);
    const segments = events.filter(event => event.start <= visibleEnd && event.end >= visibleStart)
      .map(event => ({ ...event, startColumn: Math.max(event.start, visibleStart) - weekStart + 1,
        endColumn: Math.min(event.end, visibleEnd) - weekStart + 1,
        continuesBefore: event.start < visibleStart, continuesAfter: event.end > visibleEnd }))
      .sort((a, b) => Number(b.end > b.start) - Number(a.end > a.start) || a.start - b.start || b.end - a.end || String(a.schedule.id).localeCompare(String(b.schedule.id)));
    const occupied = [];
    for (const segment of segments) {
      const fits = lane => !(occupied[lane] || []).some(other => segment.startColumn <= other.endColumn && segment.endColumn >= other.startColumn);
      let lane = previousLanes.get(segment.schedule.id) ?? 0;
      if (!fits(lane)) { lane = 0; while (!fits(lane)) lane++; }
      segment.lane = lane;
      (occupied[lane] ||= []).push(segment);
      previousLanes.set(segment.schedule.id, lane);
    }
    return { days: Array.from({ length: 7 }, (_, day) => ({ date: dateKey(weekStart + day), column: day + 1,
      outside: weekStart + day < first || weekStart + day > last })), segments, lanes: occupied.length };
  });
}
