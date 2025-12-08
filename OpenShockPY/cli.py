# This software is licensed under NNCL v1.3-MODIFIED-OpenShockPY see LICENSE.md for more info
# https://github.com/NanashiTheNameless/OpenShockPY/blob/main/LICENSE.md
import argparse
import json
import os
import sys

import keyring  # type: ignore

from .client import OpenShockClient, OpenShockPYError


def get_stored_api_key() -> str:
    """Get API key from keyring storage."""
    if keyring is None:
        raise OpenShockPYError(
            "Keyring not installed. Install with: pip install Nanashi-OpenShockPY[cli]"
        )
    api_key = keyring.get_password("openshock", "api_key")
    return api_key or ""


def set_stored_api_key(api_key: str) -> None:
    """Store API key in keyring."""
    if keyring is None:
        raise OpenShockPYError(
            "Keyring not installed. Install with: pip install Nanashi-OpenShockPY[cli]"
        )
    keyring.set_password("openshock", "api_key", api_key)


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="python -m OpenShockPY.cli",
        description="OpenShock Python CLI (run with: python -m OpenShockPY.cli <command>)",
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
            "login",
            "logout",
        ],
        help="Command to run",
    )
    parser.add_argument("--api-key", dest="api_key", help="OpenShock API key")
    parser.add_argument(
        "--base-url",
        dest="base_url",
        default="https://api.openshock.app",
        help="Custom API base URL",
    )
    parser.add_argument(
        "--shocker-id", dest="shocker_id", help="Target shocker ID (UUID)"
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
    args = parser.parse_args()

    try:
        # Handle login command
        if args.command == "login":
            api_key = args.api_key or input("Enter your OpenShock API key: ").strip()
            if not api_key:
                raise OpenShockPYError("API key is required")
            set_stored_api_key(api_key)
            print("API key stored successfully in system keyring")
            return 0

        # Handle logout command
        if args.command == "logout":
            try:
                if keyring is None:
                    raise OpenShockPYError(
                        "Keyring not installed. Install with: pip install Nanashi-OpenShockPY[cli]"
                    )
                keyring.delete_password("openshock", "api_key")
                print("API key removed from system keyring")
            except Exception:
                # Set to empty string as fallback
                set_stored_api_key("")
                print("API key cleared from system keyring")
            return 0

        # Get API key from: --api-key flag, environment variable, or keyring
        api_key = args.api_key or os.getenv("OPENSHOCK_API_KEY")
        if not api_key:
            api_key = get_stored_api_key()
            if not api_key:
                raise OpenShockPYError(
                    "No API key found. Use 'python -m OpenShockPY.cli login' or set OPENSHOCK_API_KEY environment variable"
                )

        with OpenShockClient(
            api_key=api_key,
            base_url=args.base_url,
            user_agent="OpenShockPY-CLI/0.0.1.3",
        ) as client:
            data = None
            if args.command == "devices":
                data = client.list_devices()
            elif args.command == "shockers":
                data = client.list_shockers(args.device_id)
            elif args.command == "shock":
                if not args.shocker_id:
                    raise OpenShockPYError("--shocker-id is required for shock")
                if args.shocker_id.lower() == "all":
                    data = client.shock_all(args.intensity, args.duration)
                else:
                    data = client.shock(args.shocker_id, args.intensity, args.duration)
            elif args.command == "vibrate":
                if not args.shocker_id:
                    raise OpenShockPYError("--shocker-id is required for vibrate")
                if args.shocker_id.lower() == "all":
                    data = client.vibrate_all(args.intensity, args.duration)
                else:
                    data = client.vibrate(
                        args.shocker_id, args.intensity, args.duration
                    )
            elif args.command == "beep":
                if not args.shocker_id:
                    raise OpenShockPYError("--shocker-id is required for beep")
                if args.shocker_id.lower() == "all":
                    data = client.beep_all(args.duration)
                else:
                    data = client.beep(args.shocker_id, args.duration)
            elif args.command == "stop":
                if not args.shocker_id:
                    raise OpenShockPYError("--shocker-id is required for stop")
                if args.shocker_id.lower() == "all":
                    data = client.stop_all()
                else:
                    data = client.stop(args.shocker_id)
            if data is not None:
                print(json.dumps(data, indent=2))
        return 0
    except OpenShockPYError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
