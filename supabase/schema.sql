-- FF Account API — Supabase schema
-- Paste di SQL Editor, Run sekali.

create table if not exists accounts (
    uid           text primary key,
    password      text not null,
    nickname      text,
    open_id       text,
    access_token  text,
    account_id    bigint,
    region        text,
    jwt           text,
    session_key   text,
    session_iv    text,
    created_at    timestamptz default now()
);

create index if not exists accounts_region_idx     on accounts(region);
create index if not exists accounts_created_at_idx on accounts(created_at desc);
create index if not exists accounts_account_id_idx on accounts(account_id);

create table if not exists logs (
    id         bigserial primary key,
    event      text not null,
    uid        text,
    region     text,
    error      text,
    meta       jsonb,
    created_at timestamptz default now()
);

create index if not exists logs_created_at_idx on logs(created_at desc);
create index if not exists logs_event_idx      on logs(event);

alter table accounts enable row level security;
alter table logs     enable row level security;
