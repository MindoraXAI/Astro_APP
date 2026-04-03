type DevChartRecord = {
  id: string;
  user_id: string;
  full_name: string;
  birth_date: string;
  birth_time: string;
  birth_location: string;
  created_at: string;
  raw_calculation: unknown;
  ai_reading?: { text?: string } | null;
};

type DevSessionRecord = {
  id: string;
  user_id: string;
  chart_id: string;
  title: string;
  messages: Array<{ role: string; content: string }>;
  updated_at: string;
};

const charts = new Map<string, DevChartRecord>();
const sessions = new Map<string, DevSessionRecord>();

export function saveDevChart(input: Omit<DevChartRecord, "created_at">) {
  const record: DevChartRecord = {
    ...input,
    created_at: new Date().toISOString(),
  };
  charts.set(record.id, record);
  return record;
}

export function listDevChartsByUser(userId: string) {
  return Array.from(charts.values())
    .filter((c) => c.user_id === userId)
    .sort((a, b) => (a.created_at < b.created_at ? 1 : -1));
}

export function getDevChartById(chartId: string, userId: string) {
  const record = charts.get(chartId);
  if (!record || record.user_id !== userId) {
    return null;
  }
  return record;
}

export function setDevChartReading(chartId: string, userId: string, reading: string) {
  const chart = getDevChartById(chartId, userId);
  if (!chart) return false;
  chart.ai_reading = { text: reading };
  charts.set(chartId, chart);
  return true;
}

export function getDevSession(chartId: string, userId: string) {
  const key = `${userId}:${chartId}`;
  return sessions.get(key) ?? null;
}

export function upsertDevSession(chartId: string, userId: string, messages: Array<{ role: string; content: string }>) {
  const key = `${userId}:${chartId}`;
  const existing = sessions.get(key);
  const record: DevSessionRecord = {
    id: existing?.id ?? crypto.randomUUID(),
    user_id: userId,
    chart_id: chartId,
    title: `Chart chat ${chartId.slice(0, 6)}`,
    messages,
    updated_at: new Date().toISOString(),
  };
  sessions.set(key, record);
  return record;
}
