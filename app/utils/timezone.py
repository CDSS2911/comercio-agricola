from __future__ import annotations

import json
import os
import threading
import time as pytime
from datetime import datetime, timedelta
from urllib.request import urlopen
from zoneinfo import ZoneInfo

DEFAULT_TZ_NAME = 'America/Bogota'
WORLD_TIME_API = 'https://worldtimeapi.org/api/timezone/America/Bogota'

_sync_lock = threading.Lock()
_network_base_dt: datetime | None = None
_mono_base: float | None = None
_last_sync_attempt: float = 0.0
_SYNC_INTERVAL_SECONDS = 300.0


def set_process_timezone(tz_name: str = DEFAULT_TZ_NAME) -> None:
    """
    Fuerza la zona horaria del proceso para funciones locales (datetime.now/date.today).
    No requiere cambiar la zona horaria del sistema operativo.
    """
    os.environ['TZ'] = tz_name
    if hasattr(pytime, 'tzset'):
        pytime.tzset()


def _local_now_colombia() -> datetime:
    tz_name = os.environ.get('TZ') or DEFAULT_TZ_NAME
    return datetime.now(ZoneInfo(tz_name)).replace(tzinfo=None)


def _sync_network_clock_if_needed() -> None:
    global _network_base_dt, _mono_base, _last_sync_attempt

    now_mono = pytime.monotonic()
    if _network_base_dt and _mono_base and (now_mono - _last_sync_attempt) < _SYNC_INTERVAL_SECONDS:
        return

    with _sync_lock:
        now_mono = pytime.monotonic()
        if _network_base_dt and _mono_base and (now_mono - _last_sync_attempt) < _SYNC_INTERVAL_SECONDS:
            return
        _last_sync_attempt = now_mono
        try:
            with urlopen(WORLD_TIME_API, timeout=2.5) as resp:
                payload = json.loads(resp.read().decode('utf-8'))
            dt_raw = payload.get('datetime')
            if not dt_raw:
                return
            dt = datetime.fromisoformat(dt_raw)
            _network_base_dt = dt.replace(tzinfo=None)
            _mono_base = pytime.monotonic()
        except Exception:
            # Si falla red/API, se mantiene fallback local sin romper el flujo.
            return


def now_colombia() -> datetime:
    """
    Retorna fecha/hora actual de Colombia como datetime naive (sin tzinfo).
    Intenta sincronizarse con hora real via API externa; si falla, usa reloj local.
    """
    _sync_network_clock_if_needed()
    if _network_base_dt is not None and _mono_base is not None:
        elapsed = pytime.monotonic() - _mono_base
        return _network_base_dt + timedelta(seconds=elapsed)
    return _local_now_colombia()


def today_colombia():
    """Retorna la fecha actual de Colombia."""
    return now_colombia().date()


def time_colombia():
    """Retorna la hora actual de Colombia."""
    return now_colombia().time()
