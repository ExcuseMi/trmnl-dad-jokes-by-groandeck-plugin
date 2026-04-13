import asyncio
import logging
import os
import time

import aiohttp
from quart import Quart, jsonify, abort
from modules.db import init_db, save_jokes, get_random_jokes
from modules.utils.ip_whitelist import init_ip_whitelist, require_trmnl_ip

app = Quart(__name__)
log = logging.getLogger(__name__)

GROANDECK_API_URL = "https://groandeck.com/api/v1/random"
API_KEY = os.environ.get("GROANDECK_API_KEY")
JOKE_COUNT = 4

_session: aiohttp.ClientSession | None = None
_cache_lock: asyncio.Lock | None = None
_cache = {"jokes": None, "minute": -1}


@app.before_serving
async def startup():
    global _session, _cache_lock
    _session = aiohttp.ClientSession()
    _cache_lock = asyncio.Lock()
    await asyncio.to_thread(init_db)
    init_ip_whitelist()


@app.after_serving
async def shutdown():
    if _session:
        await _session.close()


async def _fetch_one():
    async with _session.get(
        GROANDECK_API_URL,
        headers={"X-API-Key": API_KEY},
        timeout=aiohttp.ClientTimeout(total=10),
    ) as resp:
        resp.raise_for_status()
        return await resp.json()


async def _get_jokes():
    current_minute = int(time.time() // 60)
    if _cache["minute"] == current_minute:
        return _cache["jokes"]

    async with _cache_lock:
        if _cache["minute"] == current_minute:
            return _cache["jokes"]

        try:
            jokes = list(await asyncio.gather(*[_fetch_one() for _ in range(JOKE_COUNT)]))
            await asyncio.to_thread(save_jokes, jokes)
        except Exception as e:
            log.warning('GroanDeck API unavailable (%s), falling back to SQLite cache', e)
            jokes = await asyncio.to_thread(get_random_jokes, JOKE_COUNT)
            if not jokes:
                raise

        _cache["jokes"] = jokes
        _cache["minute"] = current_minute

    return _cache["jokes"]


@app.route("/")
@require_trmnl_ip
async def random_jokes():
    if not API_KEY:
        abort(500, description="GROANDECK_API_KEY not set")
    return jsonify({"jokes": await _get_jokes()})


@app.route("/health")
async def health():
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
