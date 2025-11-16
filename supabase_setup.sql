create table messages (
    id uuid primary key default gen_random_uuid(),
    listing_id text not null,
    sender_wallet text not null,
    message text not null,
    timestamp timestamp default now()
);
