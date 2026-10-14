# api/index.py
import os, time
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from lib.garena import full_flow

app = FastAPI(title="FF Account API", version="1.1.0")

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL / SUPABASE_KEY missing")

from supabase import create_client
sb = create_client(SUPABASE_URL, SUPABASE_KEY)


def _log(event, **kw):
    try:
        sb.table("logs").insert({
            "event": event,
            "uid": kw.get("uid"),
            "region": kw.get("region"),
            "error": kw.get("error"),
            "meta": {k: v for k, v in kw.items()
                     if k not in ("uid", "region", "error")} or None,
        }).execute()
    except Exception:
        pass


class CreateReq(BaseModel):
    region: Optional[str] = "IND"


@app.get("/")
def root():
    return {
        "creator": "DWR",
        "status": "API is running successfully",
        "version": "1.1.0",
        "backend": "supabase",
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "endpoints": [
            "GET  /",
            "POST /create_user/",
            "GET  /users/?limit=&offset=&region=",
            "GET  /user/{uid}",
            "DELETE /user/{uid}",
            "GET  /logs/?limit=",
            "GET  /stats/",
            "POST /bulk_create/?count=&region=",
        ],
    }


@app.post("/create_user/")
async def create_user(req: CreateReq):
    try:
        acc = await full_flow(region=req.region)
        sb.table("accounts").insert(acc).execute()
        _log("create", uid=acc["uid"], region=req.region,
             account_id=acc["account_id"])
        return {"success": True, "user": acc}
    except Exception as e:
        _log("error", error=str(e), region=req.region)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/bulk_create/")
async def bulk_create(count: int = Query(..., ge=1, le=100),
                      region: str = "IND"):
    import asyncio
    results, errors = [], []
    for i in range(count):
        try:
            acc = await full_flow(region=region)
            sb.table("accounts").insert(acc).execute()
            _log("create", uid=acc["uid"], region=region, batch=True)
            results.append(acc)
        except Exception as e:
            errors.append({"idx": i, "error": str(e)})
            _log("error", error=str(e), region=region, batch=True)
        await asyncio.sleep(0.5)
    return {"success": True, "created": len(results),
            "failed": len(errors), "users": results, "errors": errors}


@app.get("/users/")
def list_users(limit: int = Query(100, ge=1, le=1000),
               offset: int = Query(0, ge=0),
               region: Optional[str] = None):
    q = sb.table("accounts").select(
        "uid,nickname,open_id,account_id,region,created_at", count="exact")
    if region:
        q = q.eq("region", region)
    res = q.order("created_at", desc=True).range(offset, offset + limit - 1).execute()
    return {
        "success": True,
        "total": res.count,
        "limit": limit,
        "offset": offset,
        "count": len(res.data or []),
        "users": res.data or [],
    }


@app.get("/user/{uid}")
def get_user(uid: str):
    res = sb.table("accounts").select("*").eq("uid", uid).limit(1).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="user not found")
    return {"success": True, "user": res.data[0]}


@app.delete("/user/{uid}")
def delete_user(uid: str):
    res = sb.table("accounts").delete().eq("uid", uid).execute()
    _log("delete", uid=uid)
    return {"success": True, "deleted": uid, "rows": len(res.data or [])}


@app.get("/logs/")
def logs(limit: int = Query(100, ge=1, le=1000)):
    res = (sb.table("logs").select("*")
             .order("created_at", desc=True)
             .limit(limit).execute())
    return {"success": True, "count": len(res.data or []), "logs": res.data or []}


@app.get("/stats/")
def stats():
    total = sb.table("accounts").select("uid", count="exact").execute()
    rows = sb.table("accounts").select("region").execute().data or []
    regions = {}
    for r in rows:
        key = r.get("region") or "UNK"
        regions[key] = regions.get(key, 0) + 1
    log_count = sb.table("logs").select("id", count="exact").execute()
    return {
        "success": True,
        "total_users": total.count or 0,
        "total_logs": log_count.count or 0,
        "regions": regions,
        "backend": "supabase",
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
