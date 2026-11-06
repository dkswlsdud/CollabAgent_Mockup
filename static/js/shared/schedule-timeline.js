export function timelineEntries(timeline) {
  const start = timeline.start_at.replace(' ','T');
  const end = timeline.end_at.replace(' ','T');
  if (end<=start) return [];
  return (timeline.schedules || []).filter(schedule => schedule.status!=='CANCELLED' && schedule.start_at && schedule.end_at
    && schedule.end_at.replace(' ','T')>start && schedule.start_at.replace(' ','T')<end)
    .sort((a,b) => a.start_at.localeCompare(b.start_at) || a.end_at.localeCompare(b.end_at) || Number(a.id)-Number(b.id));
}
