import type { APIRoute } from "astro";
import OpenAI from "openai";
import { chatRequestSchema } from "../../lib/schemas/astro";
import { requireUserId } from "../../lib/server/auth";
import { getOptionalSupabaseServerClient } from "../../lib/server/supabase";
import { getDevChartById, upsertDevSession } from "../../lib/server/dev-store";

export const prerender = false;

function toSseLine(data: unknown) {
  return `data: ${JSON.stringify(data)}\n\n`;
}

function buildFallbackAstroResponse(payload: { chartData: Record<string, unknown>; messages: Array<{ role: string; content: string }>; userName: string }) {
  const lagna = (payload.chartData.lagna as string | undefined) ?? "Unknown";
  const moon = (payload.chartData.moon_sign as string | undefined) ?? "Unknown";
  const sun = (payload.chartData.sun_sign as string | undefined) ?? "Unknown";
  const dasha = ((payload.chartData.current_dasha as { mahadasha?: string } | undefined)?.mahadasha) ?? "Unknown";
  const latestQuestion =
    [...payload.messages].reverse().find((m) => m.role === "user")?.content ??
    "Give me guidance based on my chart.";

  return `Beloved ${payload.userName}, I am answering from deep Jyotish tradition.\n\nYour core chart pillars show Lagna ${lagna}, Moon sign ${moon}, and Sun sign ${sun}. Your active Mahadasha is ${dasha}.\n\nFor your question "${latestQuestion}": focus on disciplined action, emotional steadiness, and long-term consistency. This period rewards patience, skill-building, and clear communication more than quick shortcuts.\n\nIf you want, ask specifically about career, marriage, finance, or health and I will give a focused chart-based answer.`;
}

export const POST: APIRoute = async ({ request }) => {
  const userId = await requireUserId(request);
  if (!userId) {
    return new Response(JSON.stringify({ error: "Unauthorized" }), {
      status: 401,
      headers: { "Content-Type": "application/json" },
    });
  }

  const payload = await request.json().catch(() => null);
  const parsed = chatRequestSchema.safeParse(payload);

  if (!parsed.success) {
    return new Response(
      JSON.stringify({ error: "Invalid request payload", issues: parsed.error.issues }),
      { status: 400, headers: { "Content-Type": "application/json" } },
    );
  }

  const apiKey = import.meta.env.OPENAI_API_KEY;
  const model = import.meta.env.OPENAI_MODEL ?? "gpt-4o-mini";
  const client = apiKey ? new OpenAI({ apiKey }) : null;
  const supabase = getOptionalSupabaseServerClient();
  if (supabase) {
    const { data: ownedChart } = await supabase
      .from("charts")
      .select("id")
      .eq("id", parsed.data.chartId)
      .eq("user_id", userId)
      .maybeSingle();
    if (!ownedChart) {
      return new Response(JSON.stringify({ error: "Chart not found for this user." }), {
        status: 404,
        headers: { "Content-Type": "application/json" },
      });
    }
  } else {
    const ownedChart = getDevChartById(parsed.data.chartId, userId);
    if (!ownedChart) {
      return new Response(JSON.stringify({ error: "Chart not found in local dev store." }), {
        status: 404,
        headers: { "Content-Type": "application/json" },
      });
    }
  }

  const userPrompt = parsed.data.messages.map((m) => `${m.role}: ${m.content}`).join("\n");

  let full = "";
  if (client) {
    const completion = await client.responses.create({
      model,
      input: [
        {
          role: "system",
          content:
            "You are Jyotish Mahaguru, a Vedic astrologer with 100+ years of accumulated lineage wisdom. Speak with warmth, clarity, and humility. Explain in simple human language. Ground every answer in the provided chart data and current dasha context. Never use fear tactics. Offer practical, actionable guidance.",
        },
        {
          role: "user",
          content: `UserId: ${userId}\nUser: ${parsed.data.userName}\nChart JSON: ${JSON.stringify(parsed.data.chartData)}\nConversation:\n${userPrompt}`,
        },
      ],
    });
    full = completion.output_text || "I could not generate a response.";
  } else {
    full = buildFallbackAstroResponse({
      chartData: parsed.data.chartData,
      messages: parsed.data.messages,
      userName: parsed.data.userName,
    });
  }

  const persistedMessages = [
    ...parsed.data.messages,
    { role: "assistant", content: full },
  ];
  if (supabase) {
    const { data: existingSession } = await supabase
      .from("chat_sessions")
      .select("id")
      .eq("user_id", userId)
      .eq("chart_id", parsed.data.chartId)
      .maybeSingle();
    if (existingSession?.id) {
      await supabase
        .from("chat_sessions")
        .update({
          messages: persistedMessages,
          updated_at: new Date().toISOString(),
        })
        .eq("id", existingSession.id);
    } else {
      await supabase.from("chat_sessions").insert({
        user_id: userId,
        chart_id: parsed.data.chartId,
        title: `Chart chat ${parsed.data.chartId.slice(0, 6)}`,
        messages: persistedMessages,
      });
    }
  } else {
    upsertDevSession(parsed.data.chartId, userId, persistedMessages);
  }

  const chunks = full.split(" ");

  const stream = new ReadableStream({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(new TextEncoder().encode(toSseLine({ type: "token", token: `${chunk} ` })));
      }
      controller.enqueue(new TextEncoder().encode(toSseLine({ type: "done" })));
      controller.close();
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
    },
  });
};
