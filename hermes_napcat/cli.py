"""CLI entry point: ``hermes-napcat``."""
from __future__ import annotations

import argparse
import shutil
import socket
import subprocess
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


def _port_owner(port: int) -> str:
    """Return a short process name listening on the port, or ''."""
    import re
    if shutil.which("ss"):
        try:
            out = subprocess.run(
                ["ss", "-tlnp", f"sport = :{port}"],
                capture_output=True, text=True, timeout=2,
            ).stdout
            m = re.search(r'users:\(\("([^"]+)"', out)
            if m:
                return m.group(1)
        except Exception:
            pass
    if shutil.which("lsof"):
        try:
            out = subprocess.run(
                ["lsof", "-i", f":{port}", "-sTCP:LISTEN", "-Fc"],
                capture_output=True, text=True, timeout=2,
            ).stdout
            m = re.search(r'^c(.+)$', out, re.MULTILINE)
            if m:
                return m.group(1)
        except Exception:
            pass
    return ""


def _ask_port(prompt: str, default: int) -> int:
    """Prompt for a port, warn if already in use, let user pick another."""
    while True:
        port = _ask_int(prompt, default)
        if not (1 <= port <= 65535):
            print(f"    Port must be between 1 and 65535.")
            continue
        if _port_in_use(port):
            owner = _port_owner(port)
            detail = f": {owner}" if owner else ""
            print(f"    ! Port {port} is already in use{detail}")
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
    """Run the full interactive configuration wizard.
    Returns a dict with all setup parameters.
    """
    print("\n" + "=" * 52)
    print("  hermes-napcat Interactive Setup")
    print("=" * 52)
    print("  Press Enter to accept the default [shown in brackets].\n")

    # ── Hermes location ───────────────────────────────────────────────────────
    print("  Hermes Agent location:")
    hermes_dir = _ask("Path to hermes-agent source (blank = auto-detect)", "")
    hermes_dir = hermes_dir or None

    print()

    # ── QQ number ─────────────────────────────────────────────────────────────
    print("  QQ account:")
    qq = _ask("QQ number (blank = skip, configure later)", "") or None

    print()

    # ── Admins ────────────────────────────────────────────────────────────────
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

    # ── Ports ─────────────────────────────────────────────────────────────────
    print("  Network ports:")
    ws_port   = _ask_port("Hermes reverse-WS port (NapCat dials into Hermes)", 18800)
    http_port = _ask_port("NapCat HTTP API port  (Hermes calls NapCat)", 18801)

    print()

    # ── Access token ──────────────────────────────────────────────────────────
    print("  Security:")
    access_token = _ask("Access token (blank = no auth)", "")

    print()

    # ── Summary ───────────────────────────────────────────────────────────────
    print("  ── Summary " + "─" * 40)
    print(f"  Hermes dir:   {hermes_dir or '(auto-detect)'}")
    print(f"  QQ number:    {qq or '(none)'}")
    print(f"  Admins:       {', '.join(admins) if admins else '(open mode)'}")
    print(f"  WS port:      {ws_port}")
    print(f"  HTTP port:    {http_port}")
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
        hermes_dir=hermes_dir,
        qq=qq,
        admins=admins,
        ws_port=ws_port,
        http_port=http_port,
        access_token=access_token,
    )


# ── CLI ───────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> None:
    from .installer import install, uninstall, status

    parser = argparse.ArgumentParser(
        prog="hermes-napcat",
        description="Manage the NapCat (QQ/OneBot 11) plugin for Hermes Agent",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ── install / status (Hermes patching only) ───────────────────────────────
    for name, help_text in [
        ("install", "Inject NapCat support into a local Hermes Agent installation"),
        ("status",  "Show Hermes installation status"),
    ]:
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--hermes-dir", metavar="PATH", default=None,
                       help="Path to hermes-agent source (auto-detected if omitted)")

    # ── uninstall ─────────────────────────────────────────────────────────────
    uninstall_p = sub.add_parser(
        "uninstall",
        help="Remove NapCat support (Hermes patches + config)",
    )
    uninstall_p.add_argument("--hermes-dir", metavar="PATH", default=None,
                             help="Path to hermes-agent source (auto-detected if omitted)")
    uninstall_p.add_argument("-y", "--yes", action="store_true", default=False,
                             help="Skip confirmation prompt")

    # ── setup (interactive wizard, all flags optional) ────────────────────────
    setup_p = sub.add_parser(
        "setup",
        help="Interactive setup wizard — configure everything in one go",
        description=(
            "Interactive setup: patches Hermes Agent and writes the NapCat / "
            "Hermes config. It does not install or launch NapCat.\n"
            "Run with no flags for the full interactive wizard.\n"
            "Supply flags to skip individual prompts (useful for scripting)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    setup_p.add_argument("--hermes-dir", metavar="PATH", default=None,
                         help="Path to hermes-agent source (auto-detected if omitted)")
    setup_p.add_argument("--qq", metavar="QQ_NUMBER", default=None,
                         help="Your QQ number")
    setup_p.add_argument("--admins", metavar="QQ[,QQ...]", default=None,
                         help="Comma-separated admin QQ numbers (default: your QQ number)")
    setup_p.add_argument("--ws-port", metavar="PORT", type=int, default=None,
                         help="Hermes reverse-WS port NapCat dials into (default 18800)")
    setup_p.add_argument("--http-port", metavar="PORT", type=int, default=None,
                         help="NapCat HTTP API port Hermes calls (default 18801)")
    setup_p.add_argument("--token", metavar="TOKEN", default=None,
                         help="Access token (default: none)")

    args = parser.parse_args(argv)

    try:
        if args.command == "install":
            install(args.hermes_dir)

        elif args.command == "uninstall":
            from .napcat import clean_hermes_config

            if not args.yes:
                print("\nThis will remove: Hermes patches + config")
                ans = _ask("Are you sure? (yes/no)", "no").lower()
                if ans not in ("yes", "y"):
                    print("Uninstall cancelled.")
                    return

            print("\nRemoving Hermes patches...")
            uninstall(args.hermes_dir)
            ok, msg = clean_hermes_config()
            if ok:
                print(f"  [+] Cleaned ~/.hermes/config.yaml: {msg}")
            else:
                print(f"  [!] Config cleanup: {msg}")

            print("\n✓ Uninstall complete.")

        elif args.command == "status":
            status(args.hermes_dir)

        elif args.command == "setup":
            from .napcat import setup

            # Determine if any flags were supplied to skip the wizard
            flags_supplied = any([
                args.hermes_dir, args.qq,
                args.admins is not None,
                args.ws_port is not None, args.http_port is not None,
                args.token is not None,
            ])

            if flags_supplied or not sys.stdin.isatty():
                # Non-interactive: use flags, fill defaults for anything omitted
                admins = _parse_admins(args.admins or "", args.qq) if (args.admins or args.qq) else []
                cfg = dict(
                    hermes_dir=args.hermes_dir,
                    qq=args.qq,
                    admins=admins,
                    ws_port=args.ws_port if args.ws_port is not None else 18800,
                    http_port=args.http_port if args.http_port is not None else 18801,
                    access_token=args.token or "",
                )
                if not sys.stdin.isatty() and not flags_supplied:
                    print("Non-interactive: using all defaults (ports 18800/18801).")
            else:
                # Full interactive wizard
                cfg = _interactive_setup()

            setup(**cfg)

    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
