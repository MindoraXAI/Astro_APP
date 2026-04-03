import type { APIRoute } from "astro";
import Stripe from "stripe";
import { requireUserId } from "../../lib/server/auth";
import { getSupabaseServerClient } from "../../lib/server/supabase";

export const prerender = false;

const allowedPlans = ["pro_monthly", "pro_yearly", "lifetime"] as const;
type PlanCode = (typeof allowedPlans)[number];

function getPriceId(plan: PlanCode): string | undefined {
  const map: Record<PlanCode, string | undefined> = {
    pro_monthly: import.meta.env.STRIPE_PRICE_PRO_MONTHLY,
    pro_yearly: import.meta.env.STRIPE_PRICE_PRO_YEARLY,
    lifetime: import.meta.env.STRIPE_PRICE_LIFETIME,
  };
  return map[plan];
}

export const POST: APIRoute = async ({ request }) => {
  const userId = await requireUserId(request);
  if (!userId) {
    return new Response(JSON.stringify({ error: "Unauthorized" }), {
      status: 401,
      headers: { "Content-Type": "application/json" },
    });
  }

  const stripeKey = import.meta.env.STRIPE_SECRET_KEY;
  if (!stripeKey) {
    return new Response(JSON.stringify({ error: "STRIPE_SECRET_KEY is not configured." }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }

  const payload = await request.json().catch(() => null);
  const plan = payload?.plan as PlanCode | undefined;
  if (!plan || !allowedPlans.includes(plan)) {
    return new Response(JSON.stringify({ error: "Invalid plan." }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }

  const priceId = getPriceId(plan);
  if (!priceId) {
    return new Response(JSON.stringify({ error: `Missing price id for ${plan}.` }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }

  const supabase = getSupabaseServerClient();
  const { data: profile } = await supabase
    .from("profiles")
    .select("id")
    .eq("id", userId)
    .maybeSingle();
  if (!profile) {
    await supabase.from("profiles").insert({ id: userId, plan: "free" });
  }

  const stripe = new Stripe(stripeKey);
  const baseUrl = import.meta.env.PUBLIC_APP_URL ?? "http://localhost:4321";
  const mode = plan === "lifetime" ? "payment" : "subscription";
  const session = await stripe.checkout.sessions.create({
    mode,
    line_items: [{ price: priceId, quantity: 1 }],
    success_url: `${baseUrl}/app/dashboard?checkout=success`,
    cancel_url: `${baseUrl}/pricing?checkout=cancelled`,
    client_reference_id: userId,
    metadata: {
      userId,
      plan,
    },
  });

  return new Response(JSON.stringify({ url: session.url }), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
};
