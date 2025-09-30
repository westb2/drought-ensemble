import sys
import os

# Add the project root to the Python path for imports
domain_name = "potomac"
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from classes.RunOutputReader import RunOutputReader
from classes.Run import Run
from classes.Domain import Domain

TESTING = True


domain = Domain(config_file=f"{project_root}/domains/{domain_name}/config.ini", project_root=project_root, TESTING=TESTING)
domain.get_domain()
run = Run(sequence="/glade/derecho/scratch/bwest/drought-ensemble/run_sequences/spinup/spinup.json", domain=domain, output_root=None, netcdf_output=True)
run.run_full_sequence()

run_output_reader = RunOutputReader(run, processed_output_folder="processed_full_runs/spinup")
data = run_output_reader.read_output(save_to_file=True)