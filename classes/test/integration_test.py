import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from RunOutputReader import RunOutputReader
from Run import Run
from Domain import Domain

# delete the testing directory
import shutil
shutil.rmtree("domains/wolf_test/testing", ignore_errors=True)

domain = Domain(config_file="domains/wolf_test/config.ini", TESTING=True)
domain.get_domain()
run = Run(sequence_file="domains/wolf_test/run_sequences/simple_test.json", domain=domain)
run.run_full_sequence()
run_output_reader = RunOutputReader(run)
data = run_output_reader.read_output()
assert data.pressure.shape == (120, 10, 41, 78)
assert data.saturation.shape == (120, 10, 41, 78)
assert data.mask.shape == (10, 41, 78)
assert data.mannings.shape == (10, 41, 78)

print("✅ Integration test passed")