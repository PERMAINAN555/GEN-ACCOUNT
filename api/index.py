# api/index.py - v2, no supabase SDK (REST only)
import os, time
import httpx
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from lib.garena import full_flow

app = FastAPI(title="FF Account API", version="1.2.0")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
SB_REST      = f"{SUPABASE_URL}/rest/v1" if SUPABASE_URL else ""

if not (SB_REST and SUPABASE_KEY):
    raise RuntimeError("SUPABASE_URL / SUPABASE_KEY missing")


def _sb_headers(extra=None):
    h = {
        "apikey":        SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type":  "application/json",
    }
    if extra:
        h.update(extra)
    return h


def _sb_get(path, params=None):
    r = httpx.get(f"{SB_REST}/{path}", headers=_sb_headers(), params=params, timeout=15)
    if r.status_code not in (200, 206):
        raise RuntimeError(f"supabase GET {r.status_code}: {r.text[:200]}")
    return r.json()


def _sb_post(path, row, prefer="return=representation"):
    r = httpx.post(
        f"{SB_REST}/{path}", json=row,
        headers=_sb_headers({"Prefer": prefer}), timeout=15)
    if r.status_code not in (200, 201, 204):
        raise RuntimeError(f"supabase POST {r.status_code}: {r.text[:200]}")
    try:
        return r.json()
    except Exception:
        return None


def _sb_delete(path, params):
    r = httpx.delete(
        f"{SB_REST}/{path}", headers=_sb_headers({"Prefer": "return=representation"}),
        params=params, timeout=15)
    if r.status_code not in (200, 204):
        raise RuntimeError(f"supabase DELETE {r.status_code}: {r.text[:200]}")
    try:
        return r.json()
    except Exception:
        return None


def _log(event, **kw):
    try:
        row = {
            "event": event,
            "uid": kw.get("uid"),
            "region": kw.get("region"),
            "error": kw.get("error"),
            "meta": {k: v for k, v in kw.items()
                     if k not in ("uid", "region", "error")} or None,
        }
        _sb_post("logs", row, prefer="return=minimal")
    except Exception:
        pass


class CreateReq(BaseModel):
    region: Optional[str] = "IND"


@app.get("/")
def root():
    return {
        "creator": "DWR",
        "status": "API is running successfully",
        "version": "1.2.0",
        "backend": "supabase-rest",
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
        _sb_post("accounts", acc, prefer="resolution=merge-duplicates,return=minimal")
        _log("create", uid=acc["uid"], region=req.region, account_id=acc["account_id"])
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
            _sb_post("accounts", acc, prefer="resolution=merge-duplicates,return=minimal")
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
    params = {
        "select": "uid,nickname,open_id,account_id,region,created_at",
        "order":  "created_at.desc",
        "limit":  str(limit),
        "offset": str(offset),
    }
    if region:
        params["region"] = f"eq.{region}"
    rows = _sb_get("accounts", params)
    return {"success": True, "count": len(rows), "limit": limit,
            "offset": offset, "users": rows}


@app.get("/user/{uid}")
def get_user(uid: str):
    rows = _sb_get("accounts", {"uid": f"eq.{uid}", "limit": "1"})
    if not rows:
        raise HTTPException(status_code=404, detail="user not found")
    return {"success": True, "user": rows[0]}


@app.delete("/user/{uid}")
def delete_user(uid: str):
    rows = _sb_delete("accounts", {"uid": f"eq.{uid}"})
    _log("delete", uid=uid)
    return {"success": True, "deleted": uid, "rows": len(rows or [])}


@app.get("/logs/")
def logs(limit: int = Query(100, ge=1, le=1000)):
    rows = _sb_get("logs", {"order": "created_at.desc", "limit": str(limit)})
    return {"success": True, "count": len(rows), "logs": rows}


@app.get("/stats/")
def stats():
    all_rows = _sb_get("accounts", {"select": "uid,region"})
    regions = {}
    for r in all_rows:
        key = r.get("region") or "UNK"
        regions[key] = regions.get(key, 0) + 1
    log_rows = _sb_get("logs", {"select": "id"})
    return {
        "success": True,
        "total_users": len(all_rows),
        "total_logs": len(log_rows),
        "regions": regions,
        "backend": "supabase-rest",
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
