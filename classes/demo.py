import sys
import os

from RunOutputReader import RunOutputReader
from Run import Run
from Domain import Domain


domain = Domain(config_file="/Users/ben/Documents/GitHub/drought-ensemble/domains/wolf_test/config.ini", TESTING=True)
domain.get_domain()

run = Run(sequence="simple_test.json", domain=domain, output_root="/Users/ben/Desktop/drought-ensemble")
run.run_full_sequence()

run_output_reader = RunOutputReader(run)
data = run_output_reader.read_output(save_to_file=True)