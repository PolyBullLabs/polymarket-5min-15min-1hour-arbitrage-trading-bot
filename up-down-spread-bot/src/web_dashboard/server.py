"""
Flask web dashboard: API + static UI.
Run inside the bot process (--web) or standalone (reads logs/bot_state.json).
"""
import json
import shutil
import threading
import time
from pathlib import Path

from flask import Flask, jsonify, request

from market_config import apply_market_window_settings

# Project root: repository root (parent of /config, /src)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "config.json"
STATIC_DIR = Path(__file__).resolve().parent / "static"
TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"


def create_app(project_root: Path | None = None) -> Flask:
    root = project_root or PROJECT_ROOT

    app = Flask(
        __name__,
        static_folder=str(STATIC_DIR),
        template_folder=str(TEMPLATE_DIR),
    )

    @app.route("/")
    def index():
        from flask import render_template

        return render_template("index.html")

    @app.route("/api/health")
    def health():
        import web_dashboard_state as wds

        snap = wds.get_snapshot()
        ts = snap.get("updated_at", 0)
        age = time.time() - ts if ts else 9999
        file_snap = wds.read_state_file(root)
        file_ts = file_snap.get("updated_at", 0) if file_snap else 0
        file_age = time.time() - file_ts if file_ts else 9999
        bot_live = age < 15.0 or file_age < 15.0
        return jsonify(
            {
                "ok": True,
                "bot_live": bot_live,
                "snapshot_age_sec": round(min(age, file_age), 2),
            }
        )

    @app.route("/api/status")
    def api_status():
        import web_dashboard_state as wds

        snap = wds.get_snapshot()
        if snap.get("status") == "initializing" or not snap.get("coins"):
            file_snap = wds.read_state_file(root)
            if file_snap:
                return jsonify(file_snap)
        return jsonify(snap)

    @app.route("/api/config", methods=["GET"])
    def get_config():
        if not CONFIG_PATH.exists():
            return jsonify({"error": "config.json not found"}), 404
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            apply_market_window_settings(data)
            return jsonify(data)
        except (OSError, json.JSONDecodeError) as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/config", methods=["POST"])
    def post_config():
        if not request.is_json:
            return jsonify({"error": "Expected JSON body"}), 400
        body = request.get_json()
        if not isinstance(body, dict):
            return jsonify({"error": "Invalid JSON"}), 400
        apply_market_window_settings(body)
        if not CONFIG_PATH.parent.is_dir():
            CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        backup = CONFIG_PATH.with_suffix(".json.bak")
        try:
            if CONFIG_PATH.exists():
                shutil.copy2(CONFIG_PATH, backup)
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(body, f, indent=2)
            return jsonify({"ok": True, "message": "Saved. Restart the bot to apply."})
        except OSError as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/bot/stop", methods=["POST"])
    def bot_stop():
        import web_dashboard_state as wds

        wds.request_stop()
        return jsonify({"ok": True, "message": "Stop requested — bot will shut down gracefully."})

    return app


def run_server_thread(
    host: str, port: int, project_root: Path | None = None
) -> None:
    """Start Flask in a daemon thread (used by main.py --web)."""
    app = create_app(project_root or PROJECT_ROOT)

    def run():
        # Werkzeug production warning suppressed for local dashboard
        import logging

        log = logging.getLogger("werkzeug")
        log.setLevel(logging.ERROR)
        app.run(host=host, port=port, threaded=True, use_reloader=False)

    t = threading.Thread(target=run, name="WebDashboard", daemon=True)
    t.start()


if __name__ == "__main__":
    # Standalone: UI only (status from bot_state.json when bot runs with --web)
    import logging

    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    app = create_app()
    print(f"[WEB] Open http://127.0.0.1:5050 (dashboard)")
    app.run(host="127.0.0.1", port=5050, threaded=True)
