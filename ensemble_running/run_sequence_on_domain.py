import sys
import os

# Add the project root to the Python path for imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from classes.RunOutputReader import RunOutputReader
from classes.Run import Run
from classes.Domain import Domain


def run_sequence_on_domain(domain_name, sequence_path, project_root, ensemble_name, TESTING):
    domain = Domain(config_file=f"{project_root}/domains/{domain_name}/config.ini", project_root=project_root, TESTING=TESTING)
    domain.get_domain()
    run = Run(sequence=sequence_path, domain=domain, output_root=None, netcdf_output=True)
    run.run_full_sequence()

    run_output_reader = RunOutputReader(run, processed_output_folder=f"processed_full_runs/{ensemble_name}")
    data = run_output_reader.read_output(save_to_file=True)

if __name__ == "__main__":
    domain_name = sys.argv[1]
    sequence_path = sys.argv[2]
    project_root = sys.argv[3]
    ensemble_name = sys.argv[4]
    TESTING = sys.argv[5]
    run_sequence_on_domain(domain_name, sequence_path, project_root, ensemble_name, TESTING)