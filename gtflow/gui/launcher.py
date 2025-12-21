from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    """Launch the Streamlit UI via `streamlit run`.

    This wrapper exists so `gtflow-ui` works as a console script entry point.
    Any additional CLI args are forwarded to Streamlit.
    """

    try:
        from streamlit.web import cli as stcli
    except Exception as exc:
        raise RuntimeError(
            "Streamlit is required for the UI. Install with `pip install streamlit`."
        ) from exc

    app_path = str(Path(__file__).with_name("app.py"))
    argv = ["streamlit", "run", app_path, *sys.argv[1:]]
    sys.argv = argv
    raise SystemExit(stcli.main())
