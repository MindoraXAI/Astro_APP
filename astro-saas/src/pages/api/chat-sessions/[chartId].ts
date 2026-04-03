import type { APIRoute } from "astro";
import { requireUserId } from "../../../lib/server/auth";
import { getOptionalSupabaseServerClient } from "../../../lib/server/supabase";
import { getDevSession } from "../../../lib/server/dev-store";

export const prerender = false;

export const GET: APIRoute = async ({ request, params }) => {
  const userId = await requireUserId(request);
  if (!userId) {
    return new Response(JSON.stringify({ error: "Unauthorized" }), {
      status: 401,
      headers: { "Content-Type": "application/json" },
    });
  }

  const chartId = params.chartId;
  if (!chartId) {
    return new Response(JSON.stringify({ error: "Missing chart id." }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }

  const supabase = getOptionalSupabaseServerClient();
  if (!supabase) {
    return new Response(JSON.stringify({ session: getDevSession(chartId, userId) }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }

  const { data, error } = await supabase
    .from("chat_sessions")
    .select("id, title, messages, updated_at")
    .eq("user_id", userId)
    .eq("chart_id", chartId)
    .maybeSingle();

  if (error) {
    return new Response(JSON.stringify({ error: "Unable to fetch chat session." }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }

  return new Response(JSON.stringify({ session: data ?? null }), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
};
