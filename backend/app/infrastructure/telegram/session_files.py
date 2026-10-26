import base64
import io
import json
import os
import sqlite3
import struct
import tempfile
import zipfile
from pathlib import PurePosixPath

from telethon.crypto import AuthKey
from telethon.sessions import StringSession

from app.application.dto import ParsedSession, ParsedUploads

DC_IPS = {
    1: "149.154.175.53",
    2: "149.154.167.51",
    3: "149.154.175.100",
    4: "149.154.167.91",
    5: "91.108.56.130",
}

MAX_ZIP_TOTAL = 200 * 1024 * 1024
MAX_ZIP_FILES = 5000


def _telethon_string(dc_id: int, addr: str, port: int, key: bytes) -> str:
    ss = StringSession()
    ss.set_dc(dc_id, addr, port)
    ss.auth_key = AuthKey(key)
    return ss.save()


def sqlite_session_to_string(data: bytes) -> str:
    fd, path = tempfile.mkstemp(suffix=".session")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        conn = sqlite3.connect(path)
        try:
            cols = [r[1] for r in conn.execute("PRAGMA table_info(sessions)")]
            if not cols:
                raise ValueError("В файле нет таблицы sessions")
            if "server_address" in cols:  # Telethon
                row = conn.execute(
                    "SELECT dc_id, server_address, port, auth_key FROM sessions"
                ).fetchone()
                if not row or not row[3]:
                    raise ValueError("Пустая сессия Telethon")
                return _telethon_string(int(row[0]), row[1], int(row[2]), bytes(row[3]))
            if "dc_id" in cols and "auth_key" in cols:  # Pyrogram
                row = conn.execute("SELECT dc_id, auth_key FROM sessions").fetchone()
                if not row or not row[1]:
                    raise ValueError("Пустая сессия Pyrogram")
                dc = int(row[0])
                return _telethon_string(dc, DC_IPS[dc], 443, bytes(row[1]))
            raise ValueError("Неизвестный формат .session")
        finally:
            conn.close()
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def string_to_telethon(s: str) -> tuple[str, dict]:
    s = s.strip()
    if s.startswith("1") and len(s) > 300:
        StringSession(s)  # validation
        return s, {}
    raw = base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))
    api_id = None
    if len(raw) == 271:
        dc_id, api_id, _test, key, _uid, _bot = struct.unpack(">BI?256sQ?", raw)
    elif len(raw) == 267:
        dc_id, _test, key, _uid, _bot = struct.unpack(">B?256sQ?", raw)
    elif len(raw) == 263:
        dc_id, _test, key, _uid, _bot = struct.unpack(">B?256sI?", raw)
    else:
        raise ValueError("Неизвестный формат строковой сессии")
    return _telethon_string(dc_id, DC_IPS[dc_id], 443, key), (
        {"api_id": api_id} if api_id else {}
    )


def _proxy_from_meta(p) -> str | None:
    if not p:
        return None
    if isinstance(p, str):
        return p
    if isinstance(p, (list, tuple)) and len(p) >= 3:
        ptype = p[0]
        if isinstance(ptype, int):
            ptype = {1: "socks4", 2: "socks5", 3: "http"}.get(ptype, "socks5")
        user = p[4] if len(p) > 4 else None
        pwd = p[5] if len(p) > 5 else None
        auth = f"{user}:{pwd}@" if user else ""
        return f"{str(ptype).lower()}://{auth}{p[1]}:{p[2]}"
    if isinstance(p, dict) and p.get("addr"):
        auth = f"{p.get('username')}:{p.get('password')}@" if p.get("username") else ""
        return f"{p.get('proxy_type', 'socks5')}://{auth}{p['addr']}:{p['port']}"
    return None


def _meta(d: dict) -> dict:
    def first(*keys):
        for k in keys:
            if d.get(k) not in (None, ""):
                return d[k]
        return None

    api_id = first("app_id", "api_id")
    try:
        api_id = int(api_id) if api_id else None
    except (TypeError, ValueError):
        api_id = None
    phone = first("phone", "phone_number")
    return {
        "phone": str(phone) if phone else None,
        "api_id": api_id,
        "api_hash": first("app_hash", "api_hash"),
        "twofa": first("twoFA", "twofa", "2fa", "password"),
        "device_model": first("device", "device_model"),
        "system_version": first("sdk", "system_version"),
        "app_version": first("app_version"),
        "lang_code": first("lang_pack", "lang_code"),
        "system_lang_code": first("system_lang_pack", "system_lang_code"),
        "proxy": _proxy_from_meta(first("proxy")),
    }


def _expand(files: list[tuple[str, bytes]]) -> list[tuple[str, bytes]]:
    out: list[tuple[str, bytes]] = []
    for name, data in files:
        if name.lower().endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                infos = [i for i in zf.infolist() if not i.is_dir()]
                if (
                    len(infos) > MAX_ZIP_FILES
                    or sum(i.file_size for i in infos) > MAX_ZIP_TOTAL
                ):
                    raise ValueError(f"{name}: архив слишком большой")
                for i in infos:
                    if "__MACOSX" in i.filename:
                        continue
                    out.append((i.filename, zf.read(i)))
        else:
            out.append((name, data))
    return out


def parse_uploads(
    files: list[tuple[str, bytes]], string_sessions: str = ""
) -> ParsedUploads:
    result = ParsedUploads()
    try:
        flat = _expand(files)
    except (zipfile.BadZipFile, ValueError) as e:
        result.errors.append({"name": "archive", "error": str(e)})
        flat = [(n, d) for n, d in files if not n.lower().endswith(".zip")]

    sessions: dict[str, tuple[str, bytes]] = {}
    metas: dict[str, tuple[str, dict]] = {}
    for name, data in flat:
        p = PurePosixPath(name.replace("\\", "/"))
        key = str(p.with_suffix("")).lower()
        suffix = p.suffix.lower()
        if suffix == ".session":
            sessions[key] = (name, data)
        elif suffix == ".json":
            try:
                metas[key] = (name, json.loads(data.decode("utf-8-sig")))
            except (UnicodeDecodeError, json.JSONDecodeError) as e:
                result.errors.append({"name": name, "error": f"Некорректный JSON: {e}"})
        elif suffix == ".txt":
            string_sessions += "\n" + data.decode("utf-8", errors="ignore")

    for key, (name, data) in sessions.items():
        try:
            session = sqlite_session_to_string(data)
        except Exception as e:  # noqa: BLE001
            result.errors.append({"name": name, "error": str(e)})
            continue
        meta = _meta(metas.pop(key, (None, {}))[1])
        result.accounts.append(
            ParsedSession(session=session, name=name, source="session_file", **meta)
        )

    for key, (name, d) in metas.items():
        s = d.get("session_string") or d.get("string_session") or d.get("session")
        if not isinstance(s, str) or len(s) < 100:
            continue
        try:
            session, extra = string_to_telethon(s)
        except Exception as e:  # noqa: BLE001
            result.errors.append({"name": name, "error": str(e)})
            continue
        meta = _meta(d)
        meta["api_id"] = meta["api_id"] or extra.get("api_id")
        result.accounts.append(
            ParsedSession(session=session, name=name, source="json", **meta)
        )

    for i, line in enumerate(string_sessions.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            session, extra = string_to_telethon(line)
        except Exception as e:  # noqa: BLE001
            result.errors.append({"name": f"строка {i}", "error": str(e)})
            continue
        result.accounts.append(
            ParsedSession(
                session=session,
                name=f"строка {i}",
                source="string",
                api_id=extra.get("api_id"),
            )
        )
    return result


class TelethonSessionFileParser:
    def parse(
        self, files: list[tuple[str, bytes]], string_sessions: str = ""
    ) -> ParsedUploads:
        return parse_uploads(files, string_sessions)
