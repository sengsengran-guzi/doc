#!/usr/bin/env python3
"""launchd entry point for the one local JP development backend."""
import json
import os
import sys
from pathlib import Path

backend_root, options_file = sys.argv[1:3]
environment = os.environ.copy()
environment.update(json.loads(Path(options_file).read_text()))
os.chdir(backend_root)
os.execvpe("mvn", ["mvn", "spring-boot:run", "-pl", "ruoyi-admin"], environment)
