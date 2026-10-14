# lib/garena.py
import os, json, time, random, hashlib, hmac
import httpx
from .proto import (assemble_proto, parse_proto, aes_encrypt, aes_decrypt,
                    xor_open_id, AES_KEY, AES_IV)

CLIENT_SECRET = os.environ.get(
    "CLIENT_SECRET",
    "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3")
APP_ID = 100067

OAUTH_REGISTER_URL    = "https://100067.connect.garena.com/api/v2/oauth/guest:register"
OAUTH_TOKEN_URL       = "https://100067.connect.garena.com/oauth/guest/token/grant"
MAJOR_REGISTER_URL    = "https://loginbp.ppmainecoonghj.com/MajorRegister"
NEWBIE_URL            = "https://loginbp.ppmainecoonghj.com/ChooseNewbieChoice"
MAJOR_LOGIN_URL       = "https://loginbp.ppmainecoonghj.com/MajorLogin"
GENERATE_NICKNAME_URL = "https://loginbp.ppmainecoonghj.com/GenerateNickname"

FIELD_22_HEX = os.environ.get("FIELD_22_HEX", "")
if not FIELD_22_HEX:
    raise RuntimeError("FIELD_22_HEX env var missing")


async def _post(client, url, **kw):
    r = await client.post(url, **kw)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code} @ {url}")
    return r


async def register_guest(client, password):
    payload = {"app_id": APP_ID, "client_type": 2, "password": password, "source": 2}
    body = json.dumps(payload, separators=(",", ":"))
    sig = hmac.new(CLIENT_SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()
    headers = {
        "User-Agent": "GarenaMSDK/4.0.42(KB2003 ;Android 13;en;HK;app 2.130.1 2019118332;)",
        "Accept": "application/json",
        "Content-Type": "application/json; charset=utf-8",
        "Connection": "Keep-Alive",
        "Accept-Encoding": "gzip",
        "Authorization": f"Signature {sig}",
    }
    r = await _post(client, OAUTH_REGISTER_URL, data=body, headers=headers)
    d = r.json()
    if d.get("code") != 0:
        raise RuntimeError(f"register failed: {d.get('message')}")
    return str(d["data"]["uid"])


async def get_token(client, uid, password):
    payload = {
        "uid": uid, "password": password, "response_type": "token",
        "client_type": "2", "client_secret": CLIENT_SECRET, "client_id": "100067",
    }
    headers = {"User-Agent": "GarenaMSDK/4.0.30", "Accept": "application/json",
               "Accept-Encoding": "gzip", "Connection": "Keep-Alive"}
    r = await _post(client, OAUTH_TOKEN_URL, data=payload, headers=headers)
    d = r.json()
    if not d.get("access_token") or not d.get("open_id"):
        raise RuntimeError("token missing fields")
    return d["access_token"], d["open_id"]


async def generate_nickname(client, open_id):
    plain = assemble_proto({1: "en", 2: open_id})
    encrypted = aes_encrypt(plain)
    headers = {
        "Accept-Encoding": "gzip",
        "Authorization": "Bearer",
        "Connection": "Keep-Alive",
        "Content-Type": "application/x-www-form-urlencoded",
        "Host": GENERATE_NICKNAME_URL.split("/")[2],
        "ReleaseVersion": "OB55",
        "User-Agent": "UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
        "X-GA": "v1 1",
        "X-Unity-Version": "2018.4.12f1",
    }
    r = await _post(client, GENERATE_NICKNAME_URL, data=encrypted, headers=headers)
    name = r.text.strip()
    if not name:
        raise RuntimeError("empty nickname")
    return name


async def send_major_register(client, nickname, access_token, open_id, region):
    fields = {
        1: nickname, 2: access_token, 3: open_id, 5: 102000007, 6: 4, 7: 1,
        13: 1, 14: xor_open_id(open_id), 15: region, 16: 2, 20: "2.133.8", 21: 1,
        22: bytes.fromhex(FIELD_22_HEX),
    }
    encrypted = aes_encrypt(assemble_proto(fields))
    headers = {
        "Host": MAJOR_REGISTER_URL.split("/")[2],
        "User-Agent": "UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
        "Accept": "*/*", "Accept-Encoding": "deflate, gzip",
        "X-GA-SV": str(int(time.time())), "Authorization": "Bearer",
        "X-GA": "v1 1", "ReleaseVersion": "OB55",
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Unity-Version": "2018.4.12f1",
    }
    r = await _post(client, MAJOR_REGISTER_URL, data=encrypted, headers=headers)
    parsed = parse_proto(r.content)
    aid = parsed.get(3)
    if not aid:
        raise RuntimeError("no account_id")
    return int(aid)


async def send_newbie(client, account_id, choice=3):
    plain = assemble_proto({1: int(account_id), 2: 1, 3: int(choice)})
    encrypted = aes_encrypt(plain)
    headers = {
        "Host": "loginbp.ppmainecoonghj.com",
        "User-Agent": "UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
        "Accept": "*/*", "Accept-Encoding": "deflate, gzip",
        "X-GA-SV": str(int(time.time())), "Authorization": "Bearer",
        "X-GA": "v1 1", "ReleaseVersion": "OB55",
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Unity-Version": "2018.4.12f1",
    }
    await _post(client, NEWBIE_URL, data=encrypted, headers=headers)
    return True


async def send_major_login(client, access_token, open_id, region, platform="4"):
    fields = {
        3: time.strftime("%Y-%m-%d %H:%M:%S"), 4: "free fire", 5: 1, 7: "2.133.9",
        8: "Android OS 10 / API-29 (QP1A.190711.020/1617006012)",
        9: "Handheld", 10: "Vi India", 11: "WIFI", 12: 1600, 13: 720, 14: "320",
        15: "ARM64 FP ASIMD AES | 2301 | 8", 16: 2799, 17: "PowerVR Rogue GE8320",
        18: "OpenGL ES 3.2 build 1.11@5425693",
        19: "Google|9f7d6b8b-b10c-454a-852d-06332cd498eb",
        20: f"{random.randint(1,223)}.{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}",
        21: "en", 22: open_id, 23: str(platform), 24: "Handheld",
        25: "realme RMX2189", 26: region, 29: access_token, 30: 1,
        41: "Vi India", 42: "WIFI",
        57: "1ac4b80ecf0478a44203bf8fac6120f5",
        60: 19799, 61: 2536, 62: 5056, 64: 2768, 65: 19999, 66: 2536, 67: 19799,
        73: 1, 74: "/data/app/com.dts.freefiremax-ShI7E0dK8p1IiZ785pvuVQ==/lib/arm64",
        76: 2,
        77: "38f4751a330688ab124c2c804cec90a5|/data/app/com.dts.freefiremax-ShI7E0dK8p1IiZ785pvuVQ==/base.apk",
        78: 2, 79: 2, 81: "64", 83: "2019118527", 86: "OpenGLES3", 87: 3071, 88: 4, 92: 67920,
        93: "android_max",
        94: "KqsHT+UrR1HKqb6+1db+Ofei+NtZr2+hbiBo3yKDL8w+8E3S5qF2IgEEe1fFQFyHRzl4iyHjHp+QsfeLbjJ6+DidTiKxm0ak2uYYa6QR4nAUdlZR",
        95: 111107, 96: '{"cur_rate":null,"support_etc2":true}', 97: 1, 98: 1,
        99: "4", 100: "4", 102: "", 104: 83812, 105: 1,
        106: "https://dl-bs.ggpolarbear.com/live/ABHotUpdates/|https://core-bs.ggpolarbear.com/live/ABHotUpdates/|a4332cb1c1a84e51dd77441e4856ed5a",
        107: "1.9393e7b8e53e8aeb",
    }
    encrypted = aes_encrypt(assemble_proto(fields))
    headers = {
        "Host": "loginbp.ppmainecoonghj.com",
        "User-Agent": "UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
        "Accept": "*/*", "Accept-Encoding": "deflate, gzip",
        "X-GA-SV": str(int(time.time())), "Authorization": "Bearer",
        "X-GA": "v1 1", "ReleaseVersion": "OB55",
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Unity-Version": "2018.4.12f1",
    }
    r = await _post(client, MAJOR_LOGIN_URL, data=encrypted, headers=headers)
    raw = r.content
    for buf in (aes_decrypt(raw), raw[64:] if len(raw) > 64 else b"", raw):
        if not buf:
            continue
        try:
            parsed = parse_proto(buf)
        except Exception:
            continue
        jwt = parsed.get(8)
        if isinstance(jwt, bytes):
            try:
                jwt = jwt.decode("utf-8", "ignore")
            except Exception:
                jwt = ""
        if isinstance(jwt, str) and jwt.startswith("eyJ") and jwt.count(".") == 2:
            sixteen = []
            for fnum in sorted(parsed.keys()):
                v = parsed[fnum]
                vals = v if isinstance(v, list) else [v]
                for val in vals:
                    if isinstance(val, (bytes, bytearray)) and len(val) == 16:
                        sixteen.append(bytes(val))
            k = sixteen[-2] if len(sixteen) >= 2 else AES_KEY
            iv = sixteen[-1] if len(sixteen) >= 2 else AES_IV
            return jwt, k, iv
    raise RuntimeError("no JWT")


async def full_flow(region="IND", retries=3):
    password = hashlib.sha256(os.urandom(32)).hexdigest().upper()
    proxy = os.environ.get("RESIDENTIAL_PROXY") or None
    kwargs = {"timeout": 30, "verify": False}
    if proxy:
        kwargs["proxy"] = proxy
    async with httpx.AsyncClient(**kwargs) as client:
        uid = await register_guest(client, password)
        access_token, open_id = await get_token(client, uid, password)
        nickname = await generate_nickname(client, open_id)
        account_id = await send_major_register(client, nickname, access_token, open_id, region)
        await send_newbie(client, account_id, 3)
        jwt, sk, siv = await send_major_login(client, access_token, open_id, region)
    return {
        "uid": uid, "password": password, "nickname": nickname,
        "open_id": open_id, "access_token": access_token,
        "account_id": account_id, "region": region,
        "jwt": jwt, "session_key": sk.hex(), "session_iv": siv.hex(),
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
