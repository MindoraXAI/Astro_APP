import type { APIRoute } from "astro";
import OpenAI from "openai";
import { readingRequestSchema } from "../../lib/schemas/astro";
import { requireUserId } from "../../lib/server/auth";
import { getOptionalSupabaseServerClient } from "../../lib/server/supabase";
import { setDevChartReading } from "../../lib/server/dev-store";

export const prerender = false;

const readingSystemPrompt = `
You are Jyotish Guru, an expert Vedic astrologer.
Use clear and compassionate language.
Explain technical terms in plain English when used.
Return a JSON object with keys:
corePersonality, emotions, strengths, challenges, career, relationships, wealth, health, spiritualPath, currentDasha, upcomingWindows, summary.
`.trim();

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
    const parsed = readingRequestSchema.safeParse(payload);

    if (!parsed.success) {
      return new Response(
        JSON.stringify({ error: "Invalid request payload", issues: parsed.error.issues }),
        { status: 400, headers: { "Content-Type": "application/json" } },
      );
    }

    const apiKey = import.meta.env.OPENAI_API_KEY;
    let reading = "";
    if (apiKey) {
      const client = new OpenAI({ apiKey });
      const completion = await client.responses.create({
        model: import.meta.env.OPENAI_MODEL ?? "gpt-4o-mini",
        input: [
          { role: "system", content: readingSystemPrompt },
          {
            role: "user",
            content: `Name: ${parsed.data.userName}\nChart JSON:\n${JSON.stringify(parsed.data.chartData)}`,
          },
        ],
      });
      reading = completion.output_text;
    } else {
      const chart = parsed.data.chartData as Record<string, unknown>;
      const lagna = (chart.lagna as string | undefined) ?? "unknown";
      const moon = (chart.moon_sign as string | undefined) ?? "unknown";
      const sun = (chart.sun_sign as string | undefined) ?? "unknown";
      reading = `Demo reading for ${parsed.data.userName}: Your Lagna is ${lagna}, Moon sign is ${moon}, and Sun sign is ${sun}. This is local fallback mode without OpenAI key.`;
    }
    const supabase = getOptionalSupabaseServerClient();
    if (supabase) {
      const { error: updateError } = await supabase
        .from("charts")
        .update({ ai_reading: { text: reading } })
        .eq("id", parsed.data.chartId)
        .eq("user_id", userId);
      if (updateError) {
        return new Response(JSON.stringify({ error: "Reading generated but could not be saved." }), {
          status: 500,
          headers: { "Content-Type": "application/json" },
        });
      }
    } else {
      const ok = setDevChartReading(parsed.data.chartId, userId, reading);
      if (!ok) {
        return new Response(JSON.stringify({ error: "Chart not found in local dev store." }), {
          status: 404,
          headers: { "Content-Type": "application/json" },
        });
      }
    }

    return new Response(
      JSON.stringify({
        chartId: parsed.data.chartId,
        userId,
        reading,
      }),
      {
        status: 200,
        headers: { "Content-Type": "application/json" },
      },
    );
  } catch {
    return new Response(JSON.stringify({ error: "Unable to generate reading at this time." }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }
};
