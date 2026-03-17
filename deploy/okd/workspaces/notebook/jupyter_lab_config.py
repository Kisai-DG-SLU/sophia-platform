c = get_config()

c.ServerApp.ip = "0.0.0.0"
c.ServerApp.port = 8888
c.ServerApp.open_browser = False
c.ServerApp.allow_remote_access = True
c.ServerApp.allow_origin = "*"

import os
token = os.getenv("JUPYTER_TOKEN", "")
if token:
    c.ServerApp.token = token

c.ServerApp.root_dir = os.getenv("WORKSPACE_DIR", "/workspace")
c.ServerApp.preferred_dir = os.getenv("WORKSPACE_DIR", "/workspace")
