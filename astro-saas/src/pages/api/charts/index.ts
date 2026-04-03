import type { APIRoute } from "astro";
import { requireUserId } from "../../../lib/server/auth";
import { getOptionalSupabaseServerClient } from "../../../lib/server/supabase";
import { listDevChartsByUser } from "../../../lib/server/dev-store";

export const prerender = false;

export const GET: APIRoute = async ({ request }) => {
  const userId = await requireUserId(request);
  if (!userId) {
    return new Response(JSON.stringify({ error: "Unauthorized" }), {
      status: 401,
      headers: { "Content-Type": "application/json" },
    });
  }

  const supabase = getOptionalSupabaseServerClient();
  if (!supabase) {
    return new Response(JSON.stringify({ charts: listDevChartsByUser(userId), mode: "dev-bypass" }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }

  const { data, error } = await supabase
    .from("charts")
    .select("id, full_name, birth_date, birth_time, birth_location, created_at, raw_calculation, ai_reading")
    .eq("user_id", userId)
    .order("created_at", { ascending: false });

  if (error) {
    return new Response(JSON.stringify({ error: "Unable to load charts." }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }

  return new Response(JSON.stringify({ charts: data ?? [] }), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
};
