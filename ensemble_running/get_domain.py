import sys
import os

from config import TESTING
# Add the project root to the Python path for imports
domain_name = "wolf"
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from classes.RunOutputReader import RunOutputReader
from classes.Run import Run
from classes.Domain import Domain



domain = Domain(config_file=f"{project_root}/domains/{domain_name}/config.ini", project_root=project_root, TESTING=TESTING)
domain.get_domain()