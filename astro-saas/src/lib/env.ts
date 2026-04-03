const requiredServerVars = [
  "SUPABASE_SERVICE_ROLE_KEY",
  "OPENAI_API_KEY",
  "STRIPE_SECRET_KEY",
  "STRIPE_WEBHOOK_SECRET",
] as const;

type ServerVar = (typeof requiredServerVars)[number];

export function getPublicEnv() {
  return {
    supabaseUrl: import.meta.env.PUBLIC_SUPABASE_URL,
    supabaseAnonKey: import.meta.env.PUBLIC_SUPABASE_ANON_KEY,
    appUrl: import.meta.env.PUBLIC_APP_URL ?? "http://localhost:4321",
  };
}

export function assertServerEnv() {
  const missing: ServerVar[] = [];

  for (const key of requiredServerVars) {
    if (!import.meta.env[key]) {
      missing.push(key);
    }
  }

  if (missing.length > 0) {
    throw new Error(`Missing required environment variables: ${missing.join(", ")}`);
  }
}
