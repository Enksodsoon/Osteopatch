import os
from pathlib import Path

if os.name == "nt":
    appdata = Path(os.environ.get("APPDATA", ""))
    program_files = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
    paths = [program_files / "Graphviz" / "bin", appdata / "npm"]
    os.environ["PATH"] = os.pathsep.join(
        [str(path) for path in paths if path.is_dir()] + [os.environ.get("PATH", "")]
    )

from diagrams_mcp.server import mcp

mcp.run()
