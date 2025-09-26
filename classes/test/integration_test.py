import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

try:
    from ..RunOutputReader import RunOutputReader
    from ..Run import Run
    from ..Domain import Domain
except ImportError:
    from RunOutputReader import RunOutputReader
    from Run import Run
    from Domain import Domain

# delete the testing directory
import shutil
shutil.rmtree("/Users/ben/Documents/GitHub/drought-ensemble/domains/wolf_test/testing", ignore_errors=True)

domain = Domain(config_file="/Users/ben/Documents/GitHub/drought-ensemble/domains/wolf_test/config.ini", TESTING=True)
domain.get_domain()
run = Run(sequence="simple_test.json", domain=domain)
run.run_full_sequence()
run_output_reader = run.create_output_reader()
data = run_output_reader.read_output()

assert data.pressure.shape == (96, 10, 41, 78)
assert data.saturation.shape == (96, 10, 41, 78)
assert data.mask.shape == (10, 41, 78)
assert data.mannings.shape == (10, 41, 78)

print("✅ Integration test passed")