"""NapCat configuration and Hermes config management for hermes-napcat.

hermes-napcat does **not** install, launch, or manage the NapCat process —
the user runs NapCat themselves. This module only:

- writes the OneBot 11 network config so NapCat dials into Hermes (reverse WS)
  on ``ws://127.0.0.1:{ws_port}``, and
- updates ``~/.hermes/config.yaml`` with the ``napcat`` platform block.

After the Hermes gateway starts, it opens its reverse-WS listener and simply
waits for NapCat to connect.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _pip_install(package: str) -> None:
    """Install a package via pip, auto-retrying with --break-system-packages on Debian."""
    cmd = [sys.executable, "-m", "pip", "install", package, "-q"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        return
    if "externally-managed-environment" in result.stderr or "externally managed" in result.stderr:
        subprocess.run(cmd + ["--break-system-packages"], check=True)
    else:
        raise RuntimeError(f"pip install {package} failed:\n{result.stderr}")


# ── Paths ──────────────────────────────────────────────────────────────────────

def napcat_home() -> Path:
    return Path.home() / "Napcat"


def napcat_config_dir() -> Path:
    return napcat_home() / "opt" / "QQ" / "resources" / "app" / "app_launcher" / "napcat" / "config"


def onebot_config_path(qq: str | None = None) -> Path:
    d = napcat_config_dir()
    if qq:
        return d / f"onebot11_{qq}.json"
    # v4.5.3+ default config
    return d / "onebot11.json"


# ── NapCat config ──────────────────────────────────────────────────────────────

def build_napcat_config(
    ws_port: int = 18800,
    http_port: int = 18801,
    access_token: str = "",
) -> dict:
    """Build the onebot11 network config dict."""
    return {
        "network": {
            "httpServers": [
                {
                    "name": "httpServer",
                    "enable": True,
                    "port": http_port,
                    "host": "0.0.0.0",
                    "enableCors": True,
                    "enableWebsocket": True,
                    "messagePostFormat": "array",
                    "token": access_token,
                    "debug": False,
                }
            ],
            "websocketClients": [
                {
                    "name": "HermesWs",
                    "enable": True,
                    "url": f"ws://127.0.0.1:{ws_port}",
                    "messagePostFormat": "array",
                    "reportSelfMessage": False,
                    "reconnectInterval": 5000,
                    "token": access_token,
                    "debug": False,
                    "heartInterval": 30000,
                }
            ],
            "websocketServers": [],
            "httpSseServers": [],
        },
        "musicSignUrl": "",
        "enableLocalFile2Url": False,
        "parseMultMsg": False,
    }


def write_napcat_config(
    qq: str | None,
    ws_port: int = 18800,
    http_port: int = 18801,
    access_token: str = "",
) -> Path:
    """Write NapCat onebot config. Returns the config file path."""
    cfg_dir = napcat_config_dir()
    cfg_dir.mkdir(parents=True, exist_ok=True)

    cfg = build_napcat_config(ws_port, http_port, access_token)
    path = onebot_config_path(qq)
    path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")

    # Also write the default config so it works before first login
    default = onebot_config_path(None)
    if not default.exists() or qq:
        default.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")

    return path


# ── Hermes config ──────────────────────────────────────────────────────────────

def _hermes_config_path() -> Path:
    return Path.home() / ".hermes" / "config.yaml"


def _napcat_platform_block(
    http_port: int,
    access_token: str,
    ws_port: int,
    qq: str | None,
    admins: list[str] | None = None,
) -> dict:
    return {
        "enabled": True,
        "extra": {
            "http_api": f"http://127.0.0.1:{http_port}",
            "access_token": access_token,
            "self_id": qq or "YOUR_QQ_NUMBER",
            "ws_port": ws_port,
            "dm_policy": "allowlist",
            "allow_from": [],
            "admins": admins or [],
        },
    }


def write_hermes_config(
    http_port: int,
    access_token: str,
    ws_port: int,
    qq: str | None,
    admins: list[str] | None = None,
) -> tuple[bool, str]:
    """Merge the napcat platform block into ~/.hermes/config.yaml.

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

    cfg_path = _hermes_config_path()

    if cfg_path.exists():
        # Backup before modifying
        bak = cfg_path.with_suffix(".yaml.napcat.bak")
        if not bak.exists():
            import shutil
            shutil.copy2(cfg_path, bak)
        with cfg_path.open(encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    else:
        # Create minimal config so NapCat works out of the box
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg = {}

    # Merge platforms.napcat
    cfg.setdefault("platforms", {})
    if not isinstance(cfg["platforms"], dict):
        cfg["platforms"] = {}
    cfg["platforms"]["napcat"] = _napcat_platform_block(http_port, access_token, ws_port, qq, admins=admins)

    # Register toolsets: give NapCat the full Hermes CLI toolset + QQ tools
    cfg.setdefault("platform_toolsets", {})
    if not isinstance(cfg["platform_toolsets"], dict):
        cfg["platform_toolsets"] = {}
    cfg["platform_toolsets"]["napcat"] = ["hermes-cli", "hermes-napcat"]

    cfg.setdefault("group_sessions_per_user", False)

    with cfg_path.open("w", encoding="utf-8") as f:
        yaml.dump(cfg, f, allow_unicode=True, sort_keys=False, default_flow_style=False)

    return True, str(cfg_path)


def clean_hermes_config() -> tuple[bool, str]:
    """Remove napcat sections from ~/.hermes/config.yaml."""
    try:
        import yaml
    except ImportError:
        try:
            _pip_install("pyyaml")
            import yaml
        except Exception as e:
            return False, f"pyyaml not installed and auto-install failed: {e}"

    cfg_path = _hermes_config_path()
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


# ── Setup ──────────────────────────────────────────────────────────────────────

def setup(
    qq: str | None = None,
    ws_port: int = 18800,
    http_port: int = 18801,
    access_token: str = "",
    hermes_dir: str | None = None,
    admins: list[str] | None = None,
) -> None:
    """Patch Hermes + write the NapCat OneBot 11 config.

    Does not install or launch NapCat — the user runs NapCat themselves.
    """
    from .installer import install as _install_hermes

    print("\n=== hermes-napcat Setup ===\n")

    print("  [1/2] Patching Hermes Agent...")
    _install_hermes(hermes_dir)

    print("  [2/2] Writing NapCat onebot11 config...")
    cfg_path = write_napcat_config(qq, ws_port, http_port, access_token)
    print(f"  [+] Config written → {cfg_path}\n")

    _print_instructions(http_port, access_token, ws_port, qq=qq, admins=admins)


def _print_instructions(
    http_port: int,
    access_token: str,
    ws_port: int,
    qq: str | None,
    admins: list[str] | None = None,
) -> None:
    print("=" * 50)
    print("✓ Setup complete. Next steps:\n")

    step = 1
    print(f"{step}. 启动你自行安装的 NapCat（例如官方安装器）：")
    print(f"     NapCat 启动后会主动连接 Hermes 的反向 WS（ws://127.0.0.1:{ws_port}）\n")
    step += 1

    # Try to auto-write Hermes config
    ok, msg = write_hermes_config(http_port, access_token, ws_port, qq, admins=admins)
    if ok:
        print(f"{step}. Hermes config updated automatically → {msg}")
        if not qq:
            print(f"\n   ⚠  self_id is still YOUR_QQ_NUMBER — the bot won't recognise")
            print(f"      @mentions until you update it. Run:")
            print(f"      hermes-napcat setup --qq YOUR_ACTUAL_QQ_NUMBER")
        print()
    else:
        print(f"{step}. Add the following to ~/.hermes/config.yaml:\n")
        print("   platforms:")
        print("     napcat:")
        print("       enabled: true")
        print("       extra:")
        print(f'         http_api: "http://127.0.0.1:{http_port}"')
        print(f'         access_token: "{access_token}"')
        print(f'         self_id: "{qq or "YOUR_QQ_NUMBER"}"')
        print(f"         ws_port: {ws_port}")
        print('         dm_policy: "allowlist"')
        print("         allow_from: []")
        print("         admins: []             # QQ numbers that can use management commands")
        print(f"\n   (Auto-write failed: {msg})\n")
    step += 1

    print(f"{step}. Start Hermes as usual:")
    print("     hermes gateway run")
    print("     → 网关启动后仅等待 NapCat 建立连接，无需其它操作。")
    print()
