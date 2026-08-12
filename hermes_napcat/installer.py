"""Installer: installs hermes-napcat as a Hermes **plugin**.

No core Hermes source files are patched.  ``hermes-napcat setup``:

1. Copies ``hermes_napcat/plugin/`` → ``{hermes_home}/plugins/napcat/``.
2. Merges the ``platforms.napcat`` block (+ ``platform_toolsets.napcat``) into
   ``{hermes_home}/config.yaml``.

Hermes' plugin loader discovers the directory, calls ``register(ctx)``, and
the gateway connects the adapter via the platform registry — zero core code
changes, no ``.napcat.bak`` backups to maintain.

NapCat itself is never installed, launched, or configured here — you run it
and point its reverse-WebSocket item at ``ws://127.0.0.1:{ws_port}{ws_path}``.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

_PLUGIN_NAME = "napcat"


def hermes_home() -> Path:
    """Return the Hermes home directory (``$HERMES_HOME`` or ``~/.hermes``)."""
    return Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes")


def plugin_dest() -> Path:
    return hermes_home() / "plugins" / _PLUGIN_NAME


def config_path() -> Path:
    return hermes_home() / "config.yaml"


def _plugin_source() -> Path:
    return Path(__file__).parent / "plugin"


# ── pip helper (only used to install pyyaml for config editing) ───────────────

def _pip_install(package: str) -> None:
    cmd = [sys.executable, "-m", "pip", "install", package, "-q"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        return
    if "externally-managed-environment" in result.stderr or "externally managed" in result.stderr:
        subprocess.run(cmd + ["--break-system-packages"], check=True)
    else:
        raise RuntimeError(f"pip install {package} failed:\n{result.stderr}")


# ── Plugin directory ──────────────────────────────────────────────────────────

def install_plugin() -> Path:
    """Copy the bundled plugin directory into the Hermes plugins dir."""
    src = _plugin_source()
    if not (src / "plugin.yaml").exists():
        raise FileNotFoundError(f"Plugin source missing plugin.yaml at {src}")
    dst = plugin_dest()
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(
        src, dst,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
    )
    return dst


def uninstall_plugin() -> bool:
    dst = plugin_dest()
    if dst.exists():
        shutil.rmtree(dst)
        # Drop empty parent dirs (plugins/, .hermes/) so uninstall is clean.
        for parent in (dst.parent, dst.parent.parent):
            try:
                parent.rmdir()
            except OSError:
                break
        return True
    return False


# ── Hermes config ──────────────────────────────────────────────────────────────

def _napcat_platform_block(
    ws_port: int,
    ws_path: str,
    access_token: str,
    qq: str | None,
    admins: list[str] | None = None,
) -> dict:
    return {
        "enabled": True,
        "extra": {
            "ws_port": ws_port,
            "ws_path": ws_path,
            "access_token": access_token or "",
            "self_id": qq or "YOUR_QQ_NUMBER",
            "dm_policy": "allowlist",
            "allow_from": [],
            "group_policy": "open",
            "admins": admins or [],
        },
    }


def write_hermes_config(
    ws_port: int,
    ws_path: str,
    access_token: str,
    qq: str | None,
    admins: list[str] | None = None,
) -> tuple[bool, str]:
    """Merge the napcat platform block into ``~/.hermes/config.yaml``.

    Returns (success, message).
    """
    try:
        import yaml
    except ImportError:
        try:
            _pip_install("pyyaml")
            import yaml
        except Exception as e:
            return False, f"pyyaml not installed and auto-install failed: {e}"

    cfg_path = config_path()
    if cfg_path.exists():
        with cfg_path.open(encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    else:
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg = {}

    # Merge platforms.napcat
    cfg.setdefault("platforms", {})
    if not isinstance(cfg["platforms"], dict):
        cfg["platforms"] = {}
    cfg["platforms"]["napcat"] = _napcat_platform_block(
        ws_port, ws_path, access_token, qq, admins=admins
    )

    # Give NapCat the full Hermes CLI toolset + QQ tools.  (The plugin's own
    # ``hermes-napcat`` toolset is auto-enabled; ``hermes-cli`` provides the
    # terminal / file / web_search tools the agent may use from QQ.)
    cfg.setdefault("platform_toolsets", {})
    if not isinstance(cfg["platform_toolsets"], dict):
        cfg["platform_toolsets"] = {}
    cfg["platform_toolsets"]["napcat"] = ["hermes-cli", "hermes-napcat"]

    cfg.setdefault("group_sessions_per_user", False)

    with cfg_path.open("w", encoding="utf-8") as f:
        yaml.dump(cfg, f, allow_unicode=True, sort_keys=False, default_flow_style=False)

    return True, str(cfg_path)


def clean_hermes_config() -> tuple[bool, str]:
    """Remove the napcat sections from ``~/.hermes/config.yaml``."""
    try:
        import yaml
    except ImportError:
        try:
            _pip_install("pyyaml")
            import yaml
        except Exception as e:
            return False, f"pyyaml not installed and auto-install failed: {e}"

    cfg_path = config_path()
    if not cfg_path.exists():
        return False, f"Config not found: {cfg_path}"

    with cfg_path.open(encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    changed = False
    if isinstance(cfg.get("platforms"), dict) and "napcat" in cfg["platforms"]:
        del cfg["platforms"]["napcat"]
        changed = True
    if isinstance(cfg.get("platform_toolsets"), dict) and "napcat" in cfg["platform_toolsets"]:
        del cfg["platform_toolsets"]["napcat"]
        changed = True

    if changed:
        with cfg_path.open("w", encoding="utf-8") as f:
            yaml.dump(cfg, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
        return True, str(cfg_path)
    return True, "nothing to clean"


# ── Public API ────────────────────────────────────────────────────────────────

def install(
    qq: str | None = None,
    admins: list[str] | None = None,
    ws_port: int = 18801,
    ws_path: str = "/onebot/v11",
    access_token: str = "",
) -> None:
    """Install hermes-napcat as a Hermes plugin + write config."""
    print(f"\nInstalling hermes-napcat as a Hermes plugin\n")
    print(f"  Hermes home: {hermes_home()}")

    dst = install_plugin()
    print(f"  [+] Plugin copied        → {dst}")

    ok, msg = write_hermes_config(ws_port, ws_path, access_token, qq, admins=admins)
    if ok:
        print(f"  [+] Config merged        → {msg}")
    else:
        print(f"  [!] Config not written   → {msg}")
        print("      Add the platform block manually (see README).")

    print("\n✓ Plugin installed. Next steps:")
    print(f"  1. Make sure NapCat's reverse-WebSocket item points to")
    print(f"     ws://127.0.0.1:{ws_port}{ws_path}  (Universal / array format).")
    print(f"  2. Start the gateway:  hermes gateway run")
    print("     → it will discover the plugin and wait for NapCat to dial in.")


def uninstall(yes: bool = False) -> None:
    """Remove the plugin directory and its config block."""
    print(f"\nUninstalling hermes-napcat from {hermes_home()}\n")
    if install_plugin_check() and not yes:
        ans = input("  Remove the napcat plugin and its config? (yes/no): ").strip().lower()
        if ans not in ("yes", "y"):
            print("  Uninstall cancelled.")
            return

    removed = uninstall_plugin()
    print(f"  {'[-] Removed plugin' if removed else '[=] Plugin not installed'} → {plugin_dest()}")

    ok, msg = clean_hermes_config()
    if ok:
        print(f"  [+] Cleaned config: {msg}")
    else:
        print(f"  [!] Config cleanup: {msg}")

    print("\n✓ Uninstall complete. Restart the gateway for changes to take effect.")


def install_plugin_check() -> bool:
    """Return True if the plugin directory is currently installed."""
    return plugin_dest().exists()


def status() -> None:
    """Show installation status."""
    dst = plugin_dest()
    cfg = config_path()
    print(f"\nhermes-napcat status")
    print(f"  Hermes home:      {hermes_home()}")
    print(f"  plugin dir:       {'✓ ' + str(dst) if dst.exists() else '✗ not installed'}")
    manifest = dst / "plugin.yaml"
    print(f"  plugin.yaml:      {'✓' if manifest.exists() else '✗'}")
    print(f"  config.yaml:      {'✓' if cfg.exists() else '✗ missing'}")
    if dst.exists():
        py_files = [p for p in dst.rglob("*.py")]
        print(f"  plugin modules:   {len(py_files)}")
    print()
    if not dst.exists():
        print("  Run `hermes-napcat setup` to install.")
        print()
