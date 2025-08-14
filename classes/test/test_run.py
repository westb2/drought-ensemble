import os
import sys

# Handle imports for both running as module and running directly
try:    
    from ..Domain import Domain
    from ..Run import Run
except ImportError:
    # If running directly, add parent directory to path
    sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
    from Domain import Domain
    from Run import Run

domain = Domain(config_file="/Users/ben/Documents/GitHub/drought-ensemble/domains/wolf_test/config.ini", TESTING=True)

run = Run(domain=domain, sequence="simple_test.json")
run.run_full_sequence()