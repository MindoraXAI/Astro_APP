import { createClient } from "@supabase/supabase-js";

export async function requireUserId(request: Request) {
  if (import.meta.env.AUTH_BYPASS_ENABLED !== "false") {
    return import.meta.env.AUTH_BYPASS_USER_ID ?? "00000000-0000-0000-0000-000000000001";
  }

  const authHeader = request.headers.get("authorization");
  if (!authHeader?.startsWith("Bearer ")) {
    return null;
  }

  const token = authHeader.replace("Bearer ", "").trim();
  const url = import.meta.env.PUBLIC_SUPABASE_URL;
  const anonKey = import.meta.env.PUBLIC_SUPABASE_ANON_KEY;

  if (!url || !anonKey || !token) {
    return null;
  }

  const client = createClient(url, anonKey, {
    global: {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    },
    auth: {
      persistSession: false,
      autoRefreshToken: false,
    },
  });

  const { data, error } = await client.auth.getUser();
  if (error || !data.user) {
    return null;
  }

  return data.user.id;
}
