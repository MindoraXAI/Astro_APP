import type { z } from "zod";
import type { birthInputSchema } from "../schemas/astro";

type BirthInput = z.infer<typeof birthInputSchema>;

type ResolvedBirth = {
  birthLocation: string;
  timezone: string;
  latitude: number;
  longitude: number;
  confidence?: number | null;
  candidatesCount?: number | null;
};

type CalculateResult = {
  chart: unknown;
  resolvedBirth: ResolvedBirth | null;
};

const LEGACY_FETCH_TIMEOUT_MS = Number(import.meta.env.LEGACY_FETCH_TIMEOUT_MS ?? 8000);

async function fetchWithTimeout(url: string, init?: RequestInit) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), LEGACY_FETCH_TIMEOUT_MS);
  try {
    return await fetch(url, {
      ...init,
      signal: controller.signal,
    });
  } finally {
    clearTimeout(timeoutId);
  }
}

async function resolveBirthFromLegacy(legacyBackendUrl: string, birthLocation: string) {
  const url = `${legacyBackendUrl.replace(/\/$/, "")}/api/chart/resolve-location?place=${encodeURIComponent(birthLocation)}`;
  let response: Response;
  try {
    response = await fetchWithTimeout(url);
  } catch {
    return null;
  }

  if (!response.ok) {
    return null;
  }

  const resolved = await response.json();
  return {
    birthLocation: resolved.display_name ?? birthLocation,
    timezone: resolved.timezone,
    latitude: resolved.latitude,
    longitude: resolved.longitude,
    confidence: resolved.confidence ?? null,
    candidatesCount: resolved.candidates_count ?? null,
  } as ResolvedBirth;
}

export async function calculateVedicChart(input: BirthInput): Promise<CalculateResult> {
  const legacyBackendUrl = import.meta.env.LEGACY_BACKEND_URL ?? "http://127.0.0.1:8000";

  // Temporary migration bridge: reuse deterministic chart engine from legacy FastAPI
  // when available, then replace with in-repo TypeScript Swiss Ephemeris service.
  if (legacyBackendUrl) {
    const resolvedBirth = await resolveBirthFromLegacy(legacyBackendUrl, input.birthLocation);
    try {
      const response = await fetchWithTimeout(`${legacyBackendUrl.replace(/\/$/, "")}/api/chart/compute`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          full_name: input.fullName,
          date: input.birthDate,
          time: input.birthTime.length === 5 ? `${input.birthTime}:00` : input.birthTime,
          birth_place: resolvedBirth?.birthLocation ?? input.birthLocation,
          timezone: resolvedBirth?.timezone,
          latitude: resolvedBirth?.latitude,
          longitude: resolvedBirth?.longitude,
          time_confidence: "approximate",
        }),
      });

      if (response.ok) {
        return {
          chart: await response.json(),
          resolvedBirth,
        };
      }
    } catch {
      // Fallback below if the legacy service times out/unreachable.
    }
  }

  return {
    chart: {
      input,
      ayanamsa: "lahiri",
      generatedAt: new Date().toISOString(),
      planets: [],
      houses: [],
      dashaTimeline: [],
      yogas: [],
      confidence: "draft",
    },
    resolvedBirth: null,
  };
}
