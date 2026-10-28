"""Modul untuk membaca lokasi geografis asli perangkat langsung dari sensor OS Windows.

Sesuai PRD dan kebijakan sistem, koordinat tidak dipalsukan / dimock sembarangan.
Di Windows, automated Chromium/Playwright tidak menyertakan kunci Google Network Location,
sehingga API geolocation browser memerlukan bridging dari sensor Windows GeoCoordinateWatcher.
"""

from __future__ import annotations

import base64
import json
import logging
import subprocess
import sys

logger = logging.getLogger(__name__)


def get_windows_device_location(timeout_sec: float = 4.0) -> dict[str, float] | None:
    """Membaca koordinat fisik perangkat dari Windows Location Service via GeoCoordinateWatcher."""
    if sys.platform != "win32":
        return None

    script = f"""
    Add-Type -AssemblyName System.Device
    $w = New-Object System.Device.Location.GeoCoordinateWatcher
    $w.Start()
    $timeout = [DateTime]::UtcNow.AddSeconds({timeout_sec})
    while ([DateTime]::UtcNow -lt $timeout -and $w.Position.Location.IsUnknown) {{
        Start-Sleep -Milliseconds 250
    }}
    $pos = $w.Position.Location
    $w.Stop()
    if (-not $pos.IsUnknown) {{
        @{{"latitude"=$pos.Latitude; "longitude"=$pos.Longitude; "accuracy"=$pos.HorizontalAccuracy}} | ConvertTo-Json -Compress
    }}
    """
    try:
        encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
        res = subprocess.run(
            ["powershell", "-NoProfile", "-EncodedCommand", encoded],
            capture_output=True,
            text=True,
            timeout=timeout_sec + 3.0,
        )
        out = res.stdout.strip()
        if out:
            data = json.loads(out)
            lat = float(data["latitude"])
            lon = float(data["longitude"])
            acc = float(data.get("accuracy", 100.0))
            logger.info("Berhasil membaca lokasi asli perangkat: lat=%s, lon=%s, acc=%s", lat, lon, acc)
            return {
                "latitude": lat,
                "longitude": lon,
                "accuracy": acc,
            }
    except Exception as exc:
        logger.warning("Gagal membaca sensor lokasi OS Windows: %s", exc)

    return None
