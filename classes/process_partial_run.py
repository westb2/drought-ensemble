import sys
import os
import shutil

from RunOutputReader import RunOutputReader
from Run import Run
from Domain import Domain


project_root = "/glade/derecho/scratch/bwest/drought-ensemble"
domain_name = "potomac"
sequence_path = "/glade/derecho/scratch/bwest/drought-ensemble/run_sequences/simple_test/simple_test.json"

domain = Domain(config_file=f"{project_root}/domains/{domain_name}/config.ini", project_root=project_root, TESTING=False)
# domain.get_domain()
run = Run(sequence=sequence_path, domain=domain, output_root=None, netcdf_output=True)
# run.run_full_sequence()

run_output_reader = RunOutputReader(run, processed_output_folder=f"processed_full_runs")
data = run_output_reader.read_output(save_to_file=True)