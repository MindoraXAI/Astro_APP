import type { APIRoute } from "astro";
import { requireUserId } from "../../../lib/server/auth";
import { getOptionalSupabaseServerClient } from "../../../lib/server/supabase";
import { getDevChartById } from "../../../lib/server/dev-store";

export const prerender = false;

export const GET: APIRoute = async ({ request, params }) => {
  const userId = await requireUserId(request);
  if (!userId) {
    return new Response(JSON.stringify({ error: "Unauthorized" }), {
      status: 401,
      headers: { "Content-Type": "application/json" },
    });
  }

  const chartId = params.id;
  if (!chartId) {
    return new Response(JSON.stringify({ error: "Missing chart id." }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }

  const supabase = getOptionalSupabaseServerClient();
  let data: unknown = null;
  if (supabase) {
    const { data: chartData, error } = await supabase
      .from("charts")
      .select("id, full_name, birth_date, birth_time, birth_location, created_at, raw_calculation, ai_reading")
      .eq("id", chartId)
      .eq("user_id", userId)
      .maybeSingle();
    if (error) {
      return new Response(JSON.stringify({ error: "Unable to fetch chart." }), {
        status: 500,
        headers: { "Content-Type": "application/json" },
      });
    }
    data = chartData;
  } else {
    data = getDevChartById(chartId, userId);
  }

  if (!data) {
    return new Response(JSON.stringify({ error: "Chart not found." }), {
      status: 404,
      headers: { "Content-Type": "application/json" },
    });
  }

  return new Response(JSON.stringify({ chart: data }), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
};
