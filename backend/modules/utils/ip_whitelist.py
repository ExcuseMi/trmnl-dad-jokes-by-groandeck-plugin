import logging, os, threading, time
from functools import wraps
import requests
from flask import jsonify, request

TRMNL_IPS_API = 'https://trmnl.com/api/ips'
ENABLE_IP_WHITELIST = os.getenv('ENABLE_IP_WHITELIST', 'true').lower() == 'true'
IP_REFRESH_HOURS = int(os.getenv('IP_REFRESH_HOURS', '24'))
LOCALHOST_IPS = {'127.0.0.1', '::1'}

log = logging.getLogger(__name__)
_ips: set[str] = set(LOCALHOST_IPS)
_lock = threading.Lock()


def _fetch_ips() -> set[str]:
    try:
        resp = requests.get(TRMNL_IPS_API, timeout=10)
        resp.raise_for_status()
        data = resp.json().get('data', {})
        ips = set(data.get('ipv4', []) + data.get('ipv6', [])) | LOCALHOST_IPS
        log.info('Loaded %d TRMNL IPs', len(ips))
        return ips
    except Exception as e:
        log.warning('Failed to fetch TRMNL IPs: %s', e)
        return set()


def _refresh_worker():
    while True:
        time.sleep(IP_REFRESH_HOURS * 3600)
        fresh = _fetch_ips()
        if fresh:
            with _lock:
                global _ips
                _ips = fresh


def init_ip_whitelist():
    if not ENABLE_IP_WHITELIST:
        log.info('IP whitelist disabled')
        return
    fresh = _fetch_ips()
    if fresh:
        with _lock:
            global _ips
            _ips = fresh
    threading.Thread(target=_refresh_worker, daemon=True, name='ip-refresh').start()
    log.info('IP whitelist enabled — refresh every %dh', IP_REFRESH_HOURS)


def _client_ip() -> str:
    for header in ('CF-Connecting-IP', 'X-Forwarded-For', 'X-Real-IP'):
        value = request.headers.get(header)
        if value:
            return value.split(',')[0].strip()
    return request.remote_addr


def require_trmnl_ip(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not ENABLE_IP_WHITELIST:
            return f(*args, **kwargs)
        ip = _client_ip()
        with _lock:
            allowed = ip in _ips
        if not allowed:
            log.warning('Blocked request from %s', ip)
            return jsonify({'error': 'forbidden'}), 403
        return f(*args, **kwargs)
    return decorated
