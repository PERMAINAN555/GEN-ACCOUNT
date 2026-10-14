# FF Account API

FastAPI on Vercel + Supabase Postgres.

## Endpoints

| Method | Path | Notes |
|--------|------|-------|
| GET    | `/`                              | health + endpoint list |
| POST   | `/create_user/`                  | body `{"region":"ID"}` |
| POST   | `/bulk_create/?count=10&region=ID` | sequential batch |
| GET    | `/users/?limit=&offset=&region=` | paginated list |
| GET    | `/user/{uid}`                    | single record |
| DELETE | `/user/{uid}`                    | remove |
| GET    | `/logs/?limit=`                  | recent events |
| GET    | `/stats/`                        | totals + region split |

## Deploy

1. Push repo to GitHub
2. Vercel → Import → set env vars (`CLIENT_SECRET`, `FIELD_22_HEX`, `SUPABASE_URL`, `SUPABASE_KEY`)
3. Supabase → SQL Editor → run `supabase/schema.sql`
4. Deploy

## Env vars

See `.env.example`.
