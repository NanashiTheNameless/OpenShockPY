# This software is licensed under NNCL v1.3-MODIFIED-OpenShockPY see LICENSE.md for more info
# https://github.com/NanashiTheNameless/OpenShockPY/blob/main/LICENSE.md
"""Command line interface for OpenShockPY."""

import argparse
import json
import os
import sys
from typing import Any, List, Optional

import requests

from . import __version__
from ._core import DEFAULT_BASE_URL, DEFAULT_TIMEOUT
from .client import OpenShockClient, OpenShockPYError, OpenShockValidationError

try:  # keyring is an optional extra
    import keyring  # type: ignore
except ImportError:  # pragma: no cover - depends on environment
    keyring = None  # type: ignore[assignment]

KEYRING_SERVICE = "openshock"
KEYRING_USERNAME = "api_key"
_KEYRING_HINT = (
    "Keyring not installed. Install with: pip install Nanashi-OpenShockPY[cli]"
)


def _require_keyring() -> Any:
    if keyring is None:
        raise OpenShockPYError(_KEYRING_HINT)
    return keyring


def get_stored_api_key() -> str:
    """Get the API key from keyring storage."""
    return _require_keyring().get_password(KEYRING_SERVICE, KEYRING_USERNAME) or ""


def set_stored_api_key(api_key: str) -> None:
    """Store the API key in keyring."""
    _require_keyring().set_password(KEYRING_SERVICE, KEYRING_USERNAME, api_key)


def delete_stored_api_key() -> None:
    """Remove the API key from keyring, tolerating an already-empty store."""
    ring = _require_keyring()
    try:
        ring.delete_password(KEYRING_SERVICE, KEYRING_USERNAME)
    except Exception:
        # Not every backend raises PasswordDeleteError, and some cannot
        # delete at all; blanking the entry is the portable fallback.
        ring.set_password(KEYRING_SERVICE, KEYRING_USERNAME, "")


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        prog="openshock",
        description=(
            "UNOFFICIAL OpenShock CLI "
            "(also runnable as: python -m OpenShockPY.cli <command>)"
        ),
    )
    parser.add_argument(
        "command",
        choices=[
            "devices",
            "shockers",
            "shock",
            "vibrate",
            "beep",
            "stop",
            "pause",
            "unpause",
            "logs",
            "whoami",
            "tokens",
            "login",
            "logout",
        ],
        help="Command to run",
    )
    parser.add_argument("--api-key", dest="api_key", help="OpenShock API token")
    parser.add_argument(
        "--base-url",
        dest="base_url",
        default=os.getenv("OPENSHOCK_BASE_URL", DEFAULT_BASE_URL),
        help=f"Custom API base URL (default: {DEFAULT_BASE_URL})",
    )
    parser.add_argument(
        "--shocker-id",
        dest="shocker_id",
        help='Target shocker ID (UUID), or "all"',
    )
    parser.add_argument(
        "--device-id", dest="device_id", help="Device ID for filtering shockers"
    )
    parser.add_argument(
        "--intensity", type=int, default=50, help="Intensity 0-100 (default: 50)"
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=1000,
        help="Duration in ms (default: 1000, min: 300, max: 65535)",
    )
    parser.add_argument(
        "--exclusive",
        action="store_true",
        help="Cancel other running commands on the shocker",
    )
    parser.add_argument(
        "--custom-name",
        dest="custom_name",
        help="Name shown to the shocker owner in the control logs",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f"Request timeout in seconds (default: {DEFAULT_TIMEOUT})",
    )
    parser.add_argument(
        "--user-agent",
        dest="user_agent",
        default=f"OpenShockPY-CLI/{__version__}",
        help="User-Agent header sent with requests",
    )
    parser.add_argument(
        "--version", action="version", version=f"OpenShockPY {__version__}"
    )
    return parser


def _require_shocker_id(args: argparse.Namespace) -> str:
    if not args.shocker_id:
        raise OpenShockValidationError(
            f"--shocker-id is required for {args.command}"
        )
    return args.shocker_id


def _resolve_api_key(args: argparse.Namespace) -> str:
    """Resolve the API key from --api-key, the environment, then the keyring."""
    api_key = args.api_key or os.getenv("OPENSHOCK_API_KEY")
    if api_key:
        return api_key
    api_key = get_stored_api_key() if keyring is not None else ""
    if not api_key:
        raise OpenShockPYError(
            "No API key found. Use 'openshock login', set OPENSHOCK_API_KEY, "
            "or pass --api-key"
        )
    return api_key


def _run_command(client: OpenShockClient, args: argparse.Namespace) -> Any:
    command = args.command
    if command == "devices":
        return client.list_devices()
    if command == "shockers":
        return client.list_shockers(args.device_id)
    if command == "whoami":
        return client.get_self()
    if command == "tokens":
        return client.list_tokens()
    if command == "logs":
        if args.shocker_id:
            return client.get_shocker_logs(args.shocker_id)
        return client.get_logs()
    if command in ("pause", "unpause"):
        return client.pause_shocker(_require_shocker_id(args), command == "pause")
    if command == "shock":
        return client.shock(
            _require_shocker_id(args),
            args.intensity,
            args.duration,
            exclusive=args.exclusive,
            custom_name=args.custom_name,
        )
    if command == "vibrate":
        return client.vibrate(
            _require_shocker_id(args),
            args.intensity,
            args.duration,
            exclusive=args.exclusive,
            custom_name=args.custom_name,
        )
    if command == "beep":
        return client.beep(
            _require_shocker_id(args),
            args.duration,
            exclusive=args.exclusive,
            custom_name=args.custom_name,
        )
    if command == "stop":
        return client.stop(_require_shocker_id(args), custom_name=args.custom_name)
    raise OpenShockPYError(f"Unknown command: {command}")


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point. Returns the process exit code."""
    args = build_parser().parse_args(argv)

    try:
        if args.command == "login":
            api_key = args.api_key or input("Enter your OpenShock API key: ").strip()
            if not api_key:
                raise OpenShockValidationError("API key is required")
            set_stored_api_key(api_key)
            print("API key stored successfully in system keyring")
            return 0

        if args.command == "logout":
            delete_stored_api_key()
            print("API key removed from system keyring")
            return 0

        with OpenShockClient(
            api_key=_resolve_api_key(args),
            base_url=args.base_url,
            timeout=args.timeout,
            user_agent=args.user_agent,
        ) as client:
            data = _run_command(client, args)
            if data is not None:
                print(json.dumps(data, indent=2))
        return 0
    except OpenShockPYError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except requests.RequestException as e:
        print(f"Error: request failed: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:  # pragma: no cover - interactive only
        print("Aborted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
