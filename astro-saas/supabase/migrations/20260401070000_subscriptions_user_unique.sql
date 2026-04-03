alter table public.subscriptions
add constraint subscriptions_user_id_unique unique (user_id);
