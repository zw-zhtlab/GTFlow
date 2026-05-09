from __future__ import annotations

import argparse
import socket
import webbrowser

from .app import run_server


def main() -> None:
    parser = argparse.ArgumentParser(description="Launch the GTFlow local web UI.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8501)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    port = _find_port(args.host, args.port)
    url = f"http://{args.host}:{port}"
    if not args.no_browser:
        webbrowser.open(url)
    run_server(args.host, port)


def _find_port(host: str, start: int) -> int:
    for port in range(start, start + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind((host, port))
            except OSError:
                continue
            return port
    raise RuntimeError(f"No free port found from {start} to {start + 19}.")


if __name__ == "__main__":
    main()
