import sys
import os
import shutil

from RunOutputReader import RunOutputReader
from Run import Run
from Domain import Domain

project_root = "/glade/derecho/scratch/bwest/drought-ensemble"
domain = Domain(config_file=f"{project_root}/domains/wolf_test/config.ini", TESTING=True)
domain.get_domain()

shutil.rmtree(f"{project_root}/domains/wolf_test/testing", ignore_errors=True)
run = Run(sequence="simple_test.json", domain=domain, output_root="", netcdf_output=True)
run.run_full_sequence()

# run_output_reader = RunOutputReader(run)
# data = run_output_reader.read_output(save_to_file=True)