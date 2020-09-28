import os
import sys
import re
import shutil
import subprocess

from pathlib import Path, PurePosixPath
from itertools import count, chain
from subprocess import PIPE

if os.name == "nt":
    from winreg import HKEY_CURRENT_USER, OpenKey, EnumKey, QueryValueEx


INSTALL_SAGE_POSIX = "<Sage install instructions for *NIX systems>"
INSTALL_SAGE_NT = "<Sage install instructions for Windows systems>"
NO_JAVA = "This program will not run on Jython and other Java based execution environments"

SUPPORTED_VMAJ = 9


def best_version(versions):
    supported = [(vmaj, vmin) for vmaj, vmin in versions if vmaj == SUPPORTED_VMAJ]
    if supported:
        return max(supported)
    else:
        return max(versions)


def cyg_path(path, cyg_runtime):
    if cyg_runtime is None:
        return PurePosixPath(path)
    p = subprocess.run([cyg_runtime/"bin"/"cygpath.exe", str(path)], stdout=PIPE, text=True) # TODO: is Unicode handled properly?
    return PurePosixPath(p.stdout[:-1])


def cyg_bash(cyg_runtime):
    if cyg_runtime is None:
        return []
    else:
        return [cyg_runtime/"bin"/"bash.exe", "--norc", "--login"]


version_re = re.compile(r"(\d+)\.(\d+)", re.ASCII)

def version(sage, cyg_runtime):
    p = subprocess.run([*cyg_bash(cyg_runtime), sage, "--version"], stdout=PIPE, text=True)
    if m := version_re.search(p.stdout):
        vmaj, vmin = m.group(1, 2)
        return int(vmaj), int(vmin)
    else:
        raise RuntimeError(f"SageMath version could not be identified (not a sage executable?). Version string: {p.stdout}")


def get_sage_nt_locations_registry():
    assert os.name == "nt"
    sage_key_re = re.compile(r"SageMath-(\d+)\.(\d+)", re.IGNORECASE)
    with OpenKey(HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall") as root_key:
        try:
            for i in count():
                subkey_name = EnumKey(root_key, i)
                if m := sage_key_re.search(subkey_name):
                    vmaj, vmin = m.group(1, 2)
                    with OpenKey(root_key, subkey_name) as subkey:
                        location, _ = QueryValueEx(subkey, "InstallLocation")
                    yield Path(location).resolve(), vmaj, vmin
        except OSError:
            pass


def get_sage_nt_locations_appdata():
    assert os.name == "nt"
    try:
        appdata = Path(os.environ.get("LOCALAPPDATA", os.environ["APPDATA"]))
    except KeyError:
        raise RuntimeError("Cannot find the AppData folder! Is this a sane Windows site?")
    for subdir in appdata.glob("sagemath*"):
        if m := version_re.search(subdir.name):
            vmaj, vmin = m.group(1, 2)
            yield subdir.resolve(), vmaj, vmin


def get_sage_nt():
    assert os.name == "nt"
    sages_by_ver = {} #TODO: improve
    for location, vmaj, vmin in chain(get_sage_nt_locations_registry(), get_sage_nt_locations_appdata()):
        cyg_runtime = location/"runtime"
        sage = PurePosixPath(f"/opt/sagemath-{vmaj}.{vmin}/local/bin/sage")
        try:
            ver = version(sage, cyg_runtime)
        except (RuntimeError, OSError):
            continue
        sages_by_ver[ver] = (sage, cyg_runtime)

    if not sages_by_ver:
        raise RuntimeError(INSTALL_SAGE_NT)

    best_ver = best_version(sages_by_ver.keys())
    return best_ver, *sages_by_ver[best_ver]


def get_sage_posix():
    sage = shutil.which("sage")
    if sage is None:
        raise RuntimeError(INSTALL_SAGE_POSIX)
    return version(sage), sage, None


def get_sage_java():
    raise RuntimeError(NO_JAVA)


sage = None
cyg_runtime = None

def get_sage():
    global sage, cyg_runtime
    if sage is not None:
        return sage, cyg_runtime
    get_sage_by_platform = {
        "posix": get_sage_posix,
        "nt": get_sage_nt,
        "java": get_sage_java
    }
    version, sage, cyg_runtime = get_sage_by_platform[os.name]()
    vmaj, vmin = version
    if vmaj != SUPPORTED_VMAJ:
        print(f"[W] Using unsupported SageMath version {vmaj}.{vmin}", file=sys.stderr)
        print(f"[W] RSArmageddon is not supposed to work with versions other than {SUPPORTED_VMAJ}.x,", file=sys.stderr)
        print(f"[W] try installing the latest one of those before reporting a bug", file=sys.stderr)
    return sage, cyg_runtime


def run(script, *args, env=None, timeout=None):
    sage, cyg_runtime = get_sage()
    p = subprocess.run([*cyg_bash(cyg_runtime), sage, cyg_path(script, cyg_runtime), *args], env=env, timeout=timeout, stdout=PIPE, text=True)
    return p.stdout
