"""Hardware page: read-only checks for the launch monitor path.

Shows the Bluetooth adapters and service, the three Open Connect apps, and which
processes are listening on or connected to ports 921 and 9050. Nothing here
changes system state. The checks run on a worker thread because PowerShell
takes a second or two.

The launch monitor link is Bluetooth, so this page cannot confirm the monitor
itself. It reports the adapters and the apps around it.
"""

import base64
import html
import json
import logging
import subprocess
import threading
from datetime import datetime

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QPushButton, QTextBrowser, QVBoxLayout, QWidget

log = logging.getLogger(__name__)

PORTS = {921: "Open Connect (APIv1 Connect)", 9050: "GSPro"}
APPS = ["GSPro", "GSPconnect", "SQG-GSPRO-Connect"]
REFRESH_MS = 15000

# Windows device problem codes that matter most here. Others show the number.
PROBLEM_TEXT = {22: "device is disabled"}

_PS_SCRIPT = r"""
$ErrorActionPreference = 'SilentlyContinue'
$bt = @(Get-PnpDevice -Class Bluetooth | ForEach-Object {
    $p = Get-PnpDeviceProperty -InstanceId $_.InstanceId -KeyName 'DEVPKEY_Device_ProblemCode'
    [pscustomobject]@{ name = $_.FriendlyName; status = [string]$_.Status; problem = $p.Data }
})
$svc = (Get-Service bthserv).Status
$listen = @(Get-NetTCPConnection -State Listen -LocalPort 921,9050)
$est = @(Get-NetTCPConnection -State Established | Where-Object { $_.LocalPort -in 921,9050 -or $_.RemotePort -in 921,9050 })
$ownerIds = @(($listen + $est) | ForEach-Object { $_.OwningProcess } | Sort-Object -Unique)
$procs = @(Get-Process -Name GSPro,GSPconnect,SQG-GSPRO-Connect | Select-Object Name, Id)
$owners = @(Get-Process -Id $ownerIds | Select-Object Name, Id)
[pscustomobject]@{
    bluetooth = $bt
    btService = [string]$svc
    listen = @($listen | Select-Object LocalPort, OwningProcess)
    established = @($est | Select-Object LocalPort, RemotePort, OwningProcess)
    processes = $procs
    owners = $owners
} | ConvertTo-Json -Depth 4 -Compress
"""


def _run_powershell() -> dict:
    # -EncodedCommand avoids quoting problems with the multi-line script.
    encoded = base64.b64encode(_PS_SCRIPT.encode("utf-16-le")).decode("ascii")
    result = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-EncodedCommand",
            encoded,
        ],
        capture_output=True,
        text=True,
        timeout=30,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError(result.stderr.strip() or "PowerShell returned no output")
    return json.loads(result.stdout)


def _collect() -> dict:
    try:
        data = _run_powershell()
    except Exception as exc:
        log.warning("hardware check failed: %s", exc)
        return {"error": str(exc)}
    data["checked"] = datetime.now().strftime("%H:%M:%S")
    return data


def _badge(ok: bool, good: str, bad: str) -> str:
    colour = "#2e7d32" if ok else "#c62828"
    text = good if ok else bad
    return f'<span style="color:{colour}; font-weight:bold;">{html.escape(text)}</span>'


def _render(data: dict) -> str:
    if "error" in data:
        return f"<p><b>Check failed:</b> {html.escape(data['error'])}</p>"

    owners = {proc["Id"]: proc["Name"] for proc in data.get("owners", [])}
    out = []

    out.append("<h3>Bluetooth</h3>")
    out.append(f"<p>Bluetooth service: {_badge(data.get('btService') == 'Running', 'Running', data.get('btService') or 'unknown')}</p>")
    out.append("<ul>")
    for dev in data.get("bluetooth", []):
        problem = dev.get("problem") or 0
        ok = dev.get("status") == "OK" and problem == 0
        detail = "" if ok else f" ({html.escape(PROBLEM_TEXT.get(problem, f'problem code {problem}'))})"
        out.append(
            f"<li>{html.escape(dev.get('name') or '?')}: "
            f"{_badge(ok, 'OK', html.escape(dev.get('status') or '?'))}{detail}</li>"
        )
    out.append("</ul>")
    out.append(
        "<p>The launch monitor link is Bluetooth. This page does not read the paired "
        "device list, so it cannot show whether the monitor is connected.</p>"
    )

    out.append("<h3>Open Connect apps</h3><ul>")
    running = {proc["Name"]: proc["Id"] for proc in data.get("processes", [])}
    for name in APPS:
        if name in running:
            out.append(f"<li>{html.escape(name)}: {_badge(True, 'running', '')} (pid {running[name]})</li>")
        else:
            out.append(f"<li>{html.escape(name)}: {_badge(False, '', 'not running')}</li>")
    out.append("</ul>")

    out.append("<h3>Ports</h3>")
    listen = data.get("listen", [])
    established = data.get("established", [])
    for port, label in PORTS.items():
        rows = [row for row in listen if row.get("LocalPort") == port]
        out.append(f"<p><b>{port}</b> ({html.escape(label)})<br>")
        if rows:
            pid = rows[0].get("OwningProcess")
            owner = owners.get(pid, f"pid {pid}")
            out.append(f"Listening: {_badge(True, 'yes', '')} by {html.escape(owner)}<br>")
        else:
            out.append(f"Listening: {_badge(False, '', 'no')}<br>")
        peers = [
            row for row in established
            if row.get("LocalPort") == port or row.get("RemotePort") == port
        ]
        out.append(f"Connections: {len(peers)}")
        for row in peers:
            owner = owners.get(row.get("OwningProcess"), f"pid {row.get('OwningProcess')}")
            out.append(
                f"<br>&nbsp;&nbsp;{row.get('LocalPort')} to {row.get('RemotePort')} "
                f"({html.escape(owner)})"
            )
        out.append("</p>")

    out.append(
        f"<p style='color:#777'>Checked at {html.escape(data.get('checked', '?'))}. "
        "Read-only: nothing is changed.</p>"
    )
    return "".join(out)


class HardwarePage(QWidget):
    _done = Signal(object)  # emitted from the worker thread, delivered on the GUI thread

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("hardwarePage")
        self._busy = False

        self._refresh = QPushButton("Refresh")
        self._refresh.clicked.connect(self.refresh)
        self._report = QTextBrowser()
        self._report.setOpenExternalLinks(False)

        layout = QVBoxLayout(self)
        layout.addWidget(self._refresh)
        layout.addWidget(self._report, 1)

        self._done.connect(self._show)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(REFRESH_MS)
        self.refresh()

    def refresh(self) -> None:
        if self._busy:
            return
        self._busy = True
        self._refresh.setEnabled(False)
        threading.Thread(target=lambda: self._done.emit(_collect()), daemon=True).start()

    def _show(self, data: dict) -> None:
        self._busy = False
        self._refresh.setEnabled(True)
        self._report.setHtml(_render(data))


def build_hardware_page() -> QWidget:
    return HardwarePage()
