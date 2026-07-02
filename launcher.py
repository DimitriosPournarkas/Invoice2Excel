import os
import sys
import socket
import threading
import time
import webbrowser
from pathlib import Path


def _find_free_port(start: int = 8501) -> int:
    port = start
    while port < 9000:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("localhost", port)) != 0:
                return port
        port += 1
    raise RuntimeError("No free port found between 8501 and 9000.")


def _get_base_dir() -> Path:
    """Directory containing the bundled app files.
    For Nuitka onefile: temporary extraction directory (__nuitka_binary_directory).
    For normal execution: directory of this file.
    """
    nuitka_dir = globals().get("__nuitka_binary_directory")
    if nuitka_dir:
        return Path(nuitka_dir)
    return Path(__file__).parent


def _get_writable_dir() -> Path:
    """Writable directory next to the .exe for DB."""
    exe_path = Path(sys.argv[0])
    if exe_path.suffix.lower() == ".exe":
        writable = exe_path.parent
    else:
        writable = Path(__file__).parent
    # KEIN output-Ordner mehr!
    return writable


def main():
    base_dir = _get_base_dir()
    writable_dir = _get_writable_dir()
    port = _find_free_port()

    # Streamlit needs to find its own static files
    streamlit_static = base_dir / "streamlit" / "static"
    if streamlit_static.exists():
        os.environ["STREAMLIT_STATIC_PATH"] = str(streamlit_static)

    # Pass DB path to the app
    os.environ["INVOICE2EXCEL_DATA_DIR"] = str(writable_dir)

    app_path = base_dir / "app.py"

    def _open_browser():
        time.sleep(3)
        webbrowser.open(f"http://localhost:{port}")

    threading.Thread(target=_open_browser, daemon=True).start()

    from streamlit.web import cli as st_cli
    sys.argv = [
        "streamlit", "run", str(app_path),
        "--server.port", str(port),
        "--server.headless", "true",
        "--global.developmentMode", "false",
        "--server.fileWatcherType", "none",
    ]
    st_cli.main()


if __name__ == "__main__":
    main()