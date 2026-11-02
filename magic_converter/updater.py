"""Update checks against GitHub Releases, installer download and hand-off.

Each release on GitHub must be tagged ``vMAJOR.MINOR.PATCH`` and have the
Inno Setup installer (``MagicConverter-Setup-x.y.z.exe``) attached.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import APP_ID, UPDATE_REPO, __version__

API_URL = "https://api.github.com/repos/{repo}/releases/latest"
TIMEOUT = 15


class UpdateError(Exception):
    pass


class UpdateCancelled(Exception):
    pass


@dataclass(frozen=True)
class UpdateInfo:
    version: str
    notes: str
    page_url: str
    download_url: str
    asset_name: str
    size: int
    sha256: str  # empty if GitHub didn't provide a digest


def parse_version(text: str) -> tuple[int, int, int] | None:
    m = re.match(r"^\s*v?(\d+)(?:\.(\d+))?(?:\.(\d+))?\s*$", text or "", re.IGNORECASE)
    if not m:
        return None
    major, minor, patch = (int(g or 0) for g in m.groups())
    return major, minor, patch


def is_newer(remote: str, local: str = __version__) -> bool:
    r, l = parse_version(remote), parse_version(local)
    return r is not None and l is not None and r > l


def enabled() -> bool:
    return bool(re.fullmatch(r"[\w.-]+/[\w.-]+", UPDATE_REPO or ""))


def _open(url: str, accept: str):
    req = urllib.request.Request(url, headers={
        "User-Agent": f"{APP_ID}/{__version__}",
        "Accept": accept,
    })
    return urllib.request.urlopen(req, timeout=TIMEOUT)


def check_for_update() -> UpdateInfo | None:
    """Return info about a newer release, or None if up to date. Blocking."""
    if not enabled():
        return None
    try:
        with _open(API_URL.format(repo=UPDATE_REPO), "application/vnd.github+json") as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:  # repository has no releases yet
            return None
        raise UpdateError(f"The update server returned an error ({exc.code}).") from exc
    except (OSError, ValueError) as exc:
        raise UpdateError("Couldn't reach the update server. Check your internet connection.") from exc

    if data.get("draft") or data.get("prerelease"):
        return None
    tag = str(data.get("tag_name", ""))
    if not is_newer(tag):
        return None

    exes = [a for a in data.get("assets", []) if str(a.get("name", "")).lower().endswith(".exe")]
    asset = next((a for a in exes if "setup" in str(a["name"]).lower()), exes[0] if exes else None)
    if asset is None:
        return None
    digest = str(asset.get("digest") or "")
    return UpdateInfo(
        version=tag.lstrip("vV"),
        notes=str(data.get("body") or "").strip(),
        page_url=str(data.get("html_url") or ""),
        download_url=str(asset["browser_download_url"]),
        asset_name=Path(str(asset["name"])).name,
        size=int(asset.get("size") or 0),
        sha256=digest.split(":", 1)[1].lower() if digest.startswith("sha256:") else "",
    )


def download(info: UpdateInfo, progress: Callable[[float], None],
             cancel: threading.Event) -> Path:
    """Download the installer to %TEMP%, verifying size and checksum. Blocking."""
    folder = Path(tempfile.gettempdir()) / f"{APP_ID}-update"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / info.asset_name
    part = target.with_name(target.name + ".part")
    sha = hashlib.sha256()
    received = 0
    ok = False
    try:
        with _open(info.download_url, "application/octet-stream") as resp, open(part, "wb") as f:
            total = info.size or int(resp.headers.get("Content-Length") or 0)
            while chunk := resp.read(256 * 1024):
                if cancel.is_set():
                    raise UpdateCancelled()
                f.write(chunk)
                sha.update(chunk)
                received += len(chunk)
                progress(received / total if total else -1)
        if info.size and received != info.size:
            raise UpdateError("The download was incomplete. Please try again.")
        if info.sha256 and sha.hexdigest() != info.sha256:
            raise UpdateError("The download is damaged (checksum mismatch). Please try again.")
        os.replace(part, target)
        ok = True
        return target
    except OSError as exc:
        raise UpdateError("The download failed. Check your internet connection.") from exc
    finally:
        if not ok:
            part.unlink(missing_ok=True)


def launch_installer(installer: Path) -> None:
    """Start the installer silently; it closes this app, upgrades it and relaunches it."""
    flags = 0
    if sys.platform == "win32":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(
        [str(installer), "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART",
         "/CLOSEAPPLICATIONS", "/relaunch=1"],
        creationflags=flags, close_fds=True,
    )
