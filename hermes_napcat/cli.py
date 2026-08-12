"""CLI entry point: ``hermes-napcat``.

Installs hermes-napcat as a Hermes **plugin** (no core source patching) and
manages its platform config.  NapCat itself is user-managed — it dials into
our reverse-WebSocket server.
"""
from __future__ import annotations

import argparse
import socket
import sys


# ── Interactive helpers ────────────────────────────────────────────────────────

def _ask(prompt: str, default: str = "") -> str:
    """Prompt the user for a value, returning default on empty input."""
    display = f" [{default}]" if default else ""
    try:
        value = input(f"  {prompt}{display}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(0)
    return value if value else default


def _ask_int(prompt: str, default: int) -> int:
    while True:
        raw = _ask(prompt, str(default))
        try:
            return int(raw)
        except ValueError:
            print("    Please enter a number.")


def _port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _ask_port(prompt: str, default: int) -> int:
    """Prompt for a port, warn if already in use, let user pick another."""
    while True:
        port = _ask_int(prompt, default)
        if not (1 <= port <= 65535):
            print(f"    Port must be between 1 and 65535.")
            continue
        if _port_in_use(port):
            print(f"    ! Port {port} is already in use")
            choice = _ask("    Use it anyway, or pick a different port? (use/pick)", "pick").lower()
            if choice in ("use", "u"):
                return port
            continue
        return port


def _parse_admins(raw: str, qq: str | None = None) -> list[str]:
    """Parse a comma-separated admin list; prepend qq if not already present."""
    parts = [x.strip() for x in raw.split(",") if x.strip()]
    if qq and qq not in parts:
        parts.insert(0, qq)
    return parts


def _interactive_setup() -> dict:
    """Run the full interactive configuration wizard."""
    print("\n" + "=" * 52)
    print("  hermes-napcat Interactive Setup")
    print("=" * 52)
    print("  Press Enter to accept the default [shown in brackets].\n")

    print("  Hermes home (the gateway's ~/.hermes):")
    from .installer import hermes_home
    print(f"    {hermes_home()}\n")

    print("  QQ account:")
    qq = _ask("QQ number (blank = skip, configure later)", "") or None

    print()
    print("  Admin QQ numbers (can use management commands like kick, mute, etc.):")
    if qq:
        print(f"  Your QQ ({qq}) will be added as admin automatically.")
        extra_raw = _ask("Additional admin QQ numbers (comma-separated, blank = none)", "")
        admins = _parse_admins(extra_raw, qq)
    else:
        admin_raw = _ask("Admin QQ numbers (comma-separated, blank = open mode)", "")
        admins = _parse_admins(admin_raw)
    if admins:
        print(f"    Admins: {', '.join(admins)}")
    else:
        print("    No admins set — all users can run management commands (open mode)")

    print()
    print("  Reverse WebSocket (NapCat dials into Hermes):")
    ws_port = _ask_port("Reverse-WS port", 18801)
    ws_path = _ask("Reverse-WS path", "/onebot/v11")

    print()
    print("  Security:")
    access_token = _ask("NapCat 鉴权 Token (blank = no auth)", "")

    print()
    print("  ── Summary " + "─" * 40)
    print(f"  QQ number:    {qq or '(none)'}")
    print(f"  Admins:       {', '.join(admins) if admins else '(open mode)'}")
    print(f"  WS:           ws://0.0.0.0:{ws_port}{ws_path}")
    print(f"  Access token: {access_token or '(none)'}")
    print()

    while True:
        confirm = _ask("Proceed with these settings? (yes/no)", "yes").lower()
        if confirm in ("yes", "y"):
            break
        if confirm in ("no", "n"):
            print("\n  Setup cancelled.")
            sys.exit(0)

    return dict(
        qq=qq,
        admins=admins,
        ws_port=ws_port,
        ws_path=ws_path,
        access_token=access_token,
    )


# ── CLI ───────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> None:
    from .installer import install, status, uninstall

    # Windows GBK consoles crash on ✓/→ etc. — force UTF-8 output so CLI
    # messages never raise UnicodeEncodeError.
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    parser = argparse.ArgumentParser(
        prog="hermes-napcat",
        description="Manage the NapCat (QQ/OneBot 11) plugin for Hermes Agent",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    for name, help_text in [
        ("install", "Install the hermes-napcat plugin + write config (non-interactive)"),
        ("status",  "Show plugin installation status"),
    ]:
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--qq", metavar="QQ_NUMBER", default=None,
                       help="Your QQ number (bot self_id)")
        p.add_argument("--admins", metavar="QQ[,QQ...]", default=None,
                       help="Comma-separated admin QQ numbers")
        p.add_argument("--ws-port", metavar="PORT", type=int, default=18801,
                       help="Reverse-WS listen port (default 18801)")
        p.add_argument("--ws-path", metavar="PATH", default="/onebot/v11",
                       help="Reverse-WS path (default /onebot/v11)")
        p.add_argument("--token", metavar="TOKEN", default="",
                       help="NapCat 鉴权 Token (default: none)")

    uninstall_p = sub.add_parser("uninstall", help="Remove the plugin + its config")
    uninstall_p.add_argument("-y", "--yes", action="store_true", default=False,
                             help="Skip confirmation prompt")

    setup_p = sub.add_parser(
        "setup",
        help="Interactive setup wizard — install the plugin + configure everything",
        description=(
            "Interactive setup: installs hermes-napcat as a Hermes plugin and "
            "writes the napcat platform block to ~/.hermes/config.yaml. It does "
            "not install, launch, or configure NapCat.\n"
            "Run with no flags for the full interactive wizard.\n"
            "Supply flags to skip individual prompts (useful for scripting)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    setup_p.add_argument("--qq", metavar="QQ_NUMBER", default=None,
                         help="Your QQ number")
    setup_p.add_argument("--admins", metavar="QQ[,QQ...]", default=None,
                         help="Comma-separated admin QQ numbers (default: your QQ number)")
    setup_p.add_argument("--ws-port", metavar="PORT", type=int, default=None,
                         help="Reverse-WS listen port (default 18801)")
    setup_p.add_argument("--ws-path", metavar="PATH", default=None,
                         help="Reverse-WS path (default /onebot/v11)")
    setup_p.add_argument("--token", metavar="TOKEN", default=None,
                         help="NapCat 鉴权 Token (default: none)")

    args = parser.parse_args(argv)

    try:
        if args.command in ("install", "setup"):
            flags_supplied = any([
                args.qq, args.admins is not None,
                getattr(args, "ws_port", None) is not None,
                getattr(args, "ws_path", None) is not None,
                getattr(args, "token", None) is not None,
            ])

            if args.command == "setup" and not flags_supplied and sys.stdin.isatty():
                cfg = _interactive_setup()
            else:
                if not sys.stdin.isatty() and not flags_supplied:
                    print("Non-interactive: using defaults (ws://0.0.0.0:18801/onebot/v11, no token).")
                admins = _parse_admins(args.admins or "", args.qq) if (args.admins or args.qq) else []
                cfg = dict(
                    qq=args.qq,
                    admins=admins,
                    ws_port=args.ws_port if args.ws_port is not None else 18801,
                    ws_path=args.ws_path or "/onebot/v11",
                    access_token=args.token or "",
                )

            install(**cfg)

        elif args.command == "uninstall":
            uninstall(yes=args.yes)

        elif args.command == "status":
            status()

    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
