"""Preview-only launcher: runs the Trillion web app on a separate port (7788)
so the Claude preview panel can render /cosmos without disturbing the live
:7777 instance. Not used in production. Bound to localhost only.
"""
import os
import sys
from pathlib import Path

os.environ["TRILLION_PORT"] = "7788"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import web_server  # noqa: E402  (loads .env on import)

if __name__ == "__main__":
    web_server.app.run(host="127.0.0.1", port=7788, debug=False, threaded=True)
