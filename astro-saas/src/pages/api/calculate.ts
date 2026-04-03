import type { APIRoute } from "astro";
import { calculateRequestSchema } from "../../lib/schemas/astro";
import { calculateVedicChart } from "../../lib/server/calculate";
import { requireUserId } from "../../lib/server/auth";
import { getOptionalSupabaseServerClient } from "../../lib/server/supabase";
import { saveDevChart } from "../../lib/server/dev-store";

export const prerender = false;

export const POST: APIRoute = async ({ request }) => {
  try {
    const userId = await requireUserId(request);
    if (!userId) {
      return new Response(JSON.stringify({ error: "Unauthorized" }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      });
    }

    const payload = await request.json();
    const parsed = calculateRequestSchema.safeParse(payload);

    if (!parsed.success) {
      return new Response(
        JSON.stringify({ error: "Invalid request payload", issues: parsed.error.issues }),
        { status: 400, headers: { "Content-Type": "application/json" } },
      );
    }

    const result = await calculateVedicChart(parsed.data.input);
    const chart = result.chart;
    const resolvedBirth = result.resolvedBirth;
    const supabase = getOptionalSupabaseServerClient();

    if (!supabase) {
      const chartId = crypto.randomUUID();
      saveDevChart({
        id: chartId,
        user_id: userId,
        full_name: parsed.data.input.fullName,
        birth_date: parsed.data.input.birthDate,
        birth_time: parsed.data.input.birthTime.length === 5 ? `${parsed.data.input.birthTime}:00` : parsed.data.input.birthTime,
        birth_location: resolvedBirth?.birthLocation ?? parsed.data.input.birthLocation,
        raw_calculation: {
          ...(typeof chart === "object" && chart !== null ? (chart as Record<string, unknown>) : { value: chart }),
          _resolved_birth: resolvedBirth,
        },
      });

      return new Response(
        JSON.stringify({ chartId, chart, resolvedBirth, userId, plan: "free", mode: "dev-bypass" }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }

    const { data: profile } = await supabase
      .from("profiles")
      .select("id, plan")
      .eq("id", userId)
      .maybeSingle();

    if (!profile) {
      await supabase.from("profiles").insert({
        id: userId,
        full_name: parsed.data.input.fullName,
        plan: "free",
      });
    }

    const plan = profile?.plan ?? "free";
    if (plan === "free") {
      const monthStart = new Date();
      monthStart.setUTCDate(1);
      monthStart.setUTCHours(0, 0, 0, 0);

      const { count } = await supabase
        .from("charts")
        .select("id", { count: "exact", head: true })
        .eq("user_id", userId)
        .gte("created_at", monthStart.toISOString());

      if ((count ?? 0) >= 1) {
        return new Response(
          JSON.stringify({ error: "Free plan limit reached. Upgrade to Pro for unlimited charts." }),
          {
            status: 402,
            headers: { "Content-Type": "application/json" },
          },
        );
      }
    }

    const { data: insertedChart, error: insertError } = await supabase
      .from("charts")
      .insert({
        user_id: userId,
        full_name: parsed.data.input.fullName,
        birth_date: parsed.data.input.birthDate,
        birth_time: parsed.data.input.birthTime.length === 5 ? `${parsed.data.input.birthTime}:00` : parsed.data.input.birthTime,
        birth_location: resolvedBirth?.birthLocation ?? parsed.data.input.birthLocation,
        timezone: resolvedBirth?.timezone ?? "UTC",
        latitude: resolvedBirth?.latitude ?? 0,
        longitude: resolvedBirth?.longitude ?? 0,
        ayanamsa: "lahiri",
        raw_calculation: {
          ...(typeof chart === "object" && chart !== null ? (chart as Record<string, unknown>) : { value: chart }),
          _resolved_birth: resolvedBirth,
        },
      })
      .select("id")
      .single();

    if (insertError || !insertedChart) {
      return new Response(JSON.stringify({ error: "Chart computed but persistence failed." }), {
        status: 500,
        headers: { "Content-Type": "application/json" },
      });
    }

    await supabase.from("usage_events").insert({
      user_id: userId,
      event_type: "chart_generated",
      metadata: {
        chartId: insertedChart.id,
        plan,
      },
    });

    return new Response(JSON.stringify({ chartId: insertedChart.id, chart, resolvedBirth, userId, plan }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  } catch {
    return new Response(JSON.stringify({ error: "Unable to compute chart at this time." }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }
};
