import type { APIRoute } from "astro";
import Stripe from "stripe";
import { getSupabaseServerClient } from "../../../lib/server/supabase";

export const prerender = false;

export const POST: APIRoute = async ({ request }) => {
  const secretKey = import.meta.env.STRIPE_SECRET_KEY;
  const webhookSecret = import.meta.env.STRIPE_WEBHOOK_SECRET;

  if (!secretKey || !webhookSecret) {
    return new Response(JSON.stringify({ error: "Stripe env vars are not configured." }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }

  const stripe = new Stripe(secretKey);
  const signature = request.headers.get("stripe-signature");
  const body = await request.text();

  if (!signature) {
    return new Response(JSON.stringify({ error: "Missing stripe-signature header." }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }

  try {
    const event = stripe.webhooks.constructEvent(body, signature, webhookSecret);
    const supabase = getSupabaseServerClient();

    if (event.type === "checkout.session.completed") {
      const session = event.data.object as Stripe.Checkout.Session;
      const userId =
        session.metadata?.userId ??
        session.client_reference_id ??
        null;
      const plan = session.metadata?.plan;

      if (userId && plan) {
        await supabase.from("subscriptions").upsert(
          {
            user_id: userId,
            stripe_customer_id:
              typeof session.customer === "string" ? session.customer : null,
            stripe_subscription_id:
              typeof session.subscription === "string" ? session.subscription : null,
            plan: plan === "lifetime" ? "lifetime" : "pro",
            status: "active",
            current_period_end: null,
          },
          { onConflict: "user_id" },
        );

        await supabase
          .from("profiles")
          .update({ plan: plan === "lifetime" ? "lifetime" : "pro" })
          .eq("id", userId);
      }
    }

    if (event.type === "customer.subscription.deleted") {
      const sub = event.data.object as Stripe.Subscription;
      if (typeof sub.customer === "string") {
        const { data: existing } = await supabase
          .from("subscriptions")
          .select("user_id")
          .eq("stripe_customer_id", sub.customer)
          .maybeSingle();
        if (existing?.user_id) {
          await supabase
            .from("subscriptions")
            .update({ status: "cancelled" })
            .eq("user_id", existing.user_id);
          await supabase
            .from("profiles")
            .update({ plan: "free" })
            .eq("id", existing.user_id);
        }
      }
    }

    return new Response(JSON.stringify({ received: true }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  } catch {
    return new Response(JSON.stringify({ error: "Invalid webhook signature." }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }
};
