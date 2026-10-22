# Stand-in for the few parts of the wmi package that platforms/windows.py and
# device_locator.py use. Everything is read by one PowerShell call per scan.
import json
import os
import subprocess
import types

PS_TIMEOUT = 120
PS_PREFIX = "[Console]::OutputEncoding=[Text.Encoding]::UTF8; "
# Win32_BIOS comes from Get-WmiObject because Get-CimInstance turns ReleaseDate into a
# local DateTime, which can move the date by a day; the upstream code wants the raw DMTF string.
PS_SCRIPT = (
    "$WarningPreference = 'SilentlyContinue'; "
    "$ErrorActionPreference = 'Stop'; "
    "$r = [ordered]@{}; "
    "$r.Win32_ComputerSystem = @(Get-CimInstance Win32_ComputerSystem | Select-Object Manufacturer, Model, PCSystemType, SystemType); "
    "$r.Win32_BIOS = @(Get-WmiObject Win32_BIOS | Select-Object SMBIOSBIOSVersion, ReleaseDate); "
    "$r.Win32_BaseBoard = @(Get-CimInstance Win32_BaseBoard | Select-Object Manufacturer, Product); "
    "$r.Win32_Processor = @(Get-CimInstance Win32_Processor | Select-Object Manufacturer, Name, Description, NumberOfCores); "
    "$pnp = @(Get-CimInstance Win32_PnPEntity); "
    "$r.Win32_PnPEntity = @($pnp | Select-Object Name, PNPClass, PNPDeviceID, Service, ConfigManagerErrorCode); "
    "$r.DeviceProperties = @($pnp | Where-Object PNPDeviceID | "
    "Invoke-CimMethod -MethodName GetDeviceProperties -Arguments @{devicePropertyKeys = [string[]]('DEVPKEY_Device_Parent', 'DEVPKEY_Device_LocationPaths')} -ErrorAction SilentlyContinue | "
    "ForEach-Object { $_.deviceProperties } | Where-Object { $null -ne $_.Data } | Select-Object DeviceID, KeyName, Data); "
    "try { "
    "$r.WmiMonitorID = @(Get-CimInstance -Namespace root/wmi WmiMonitorID | Select-Object InstanceName, UserFriendlyName); "
    "$r.WmiMonitorConnectionParams = @(Get-CimInstance -Namespace root/wmi WmiMonitorConnectionParams | Select-Object InstanceName, VideoOutputTechnology); "
    "$r.WmiMonitorListedSupportedSourceModes = @(Get-CimInstance -Namespace root/wmi WmiMonitorListedSupportedSourceModes | "
    "ForEach-Object { [ordered]@{InstanceName = $_.InstanceName; MonitorSourceModes = @($_.MonitorSourceModes | Select-Object HorizontalActivePixels, VerticalActivePixels)} }) "
    "} catch { $r.WmiMonitorID = @(); $r.WmiMonitorConnectionParams = @(); $r.WmiMonitorListedSupportedSourceModes = @() }; "
    "$r | ConvertTo-Json -Compress -Depth 6"
)

_data = None


def _list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


class Instance(object):
    def __init__(self, values, properties=None):
        for key, value in values.items():
            # ConvertTo-Json writes a one element array of embedded objects as a bare object
            if isinstance(value, dict):
                value = [value]
            if isinstance(value, list) and value and isinstance(value[0], dict):
                value = [Instance(item) for item in value]
            self.__dict__[key] = value
        self.__dict__["_properties"] = properties or {}

    def __getattr__(self, name):
        return None

    def GetDeviceProperties(self, keys):
        # wmi returns (properties, return value); a property without data has no Data attribute
        return ([types.SimpleNamespace(**({"Data": self._properties[key]} if key in self._properties else {})) for key in keys], 0)


def parse(text):
    raw = json.loads(text)
    properties = {}
    for item in _list(raw.pop("DeviceProperties", None)):
        value = item.get("Data")
        if item.get("KeyName") == "DEVPKEY_Device_LocationPaths":
            value = _list(value)
        properties.setdefault((item.get("DeviceID") or "").upper(), {})[item.get("KeyName")] = value

    # WMI hands uint32 values to COM clients as signed VT_I4, and windows.py compares against -2147483648
    for item in _list(raw.get("WmiMonitorConnectionParams")):
        value = item.get("VideoOutputTechnology")
        if isinstance(value, int) and value >= 2 ** 31:
            item["VideoOutputTechnology"] = value - 2 ** 32

    data = {}
    for name, values in raw.items():
        data[name] = [Instance(v, properties.get((v.get("PNPDeviceID") or "").upper())) for v in _list(values)]
    return data


def _powershell(script):
    exe = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "WindowsPowerShell", "v1.0", "powershell.exe")
    try:
        completed = subprocess.run([exe, "-NoProfile", "-NonInteractive", "-Command", PS_PREFIX + script], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=PS_TIMEOUT)
    except subprocess.TimeoutExpired:
        return ("", "PowerShell did not answer within {} seconds".format(PS_TIMEOUT), 1)
    except OSError as e:
        return ("", "{} could not be started: {}".format(exe, e), 1)
    return (completed.stdout.decode("utf-8", "replace"), completed.stderr.decode("utf-8", "replace"), completed.returncode)


def snapshot():
    global _data
    out, err, code = _powershell(PS_SCRIPT)
    if code != 0 or not out.strip():
        reason = next((line.strip() for line in err.splitlines() if line.strip()), "exit code {}".format(code))
        raise Exception("PowerShell could not read the hardware information: {}".format(reason))
    try:
        _data = parse(out)
    except ValueError as e:
        raise Exception("PowerShell returned hardware information that could not be read: {}".format(e))


class WMI(object):
    def __init__(self, namespace=None):
        pass

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        if _data is None:
            snapshot()
        if name not in _data:
            raise AttributeError(name)
        return lambda: list(_data[name])
