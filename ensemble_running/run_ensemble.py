import sys
import os
import shutil

from config import TESTING
# Add the project root to the Python path for imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from classes.RunOutputReader import RunOutputReader
from classes.Run import Run
from classes.Domain import Domain

# these are the input we can change
project_root = "/glade/derecho/scratch/bwest/drought-ensemble"
domain_name = "potomac"
ensemble_name = "ensemble_1"
sequences_folder = os.path.join(project_root, "run_sequences", ensemble_name)

sequences = [f"{sequences_folder}/{sequence}" for sequence in os.listdir(sequences_folder)]
# remove any files that are not json
sequences = [sequence for sequence in sequences if sequence.endswith(".json")]

for sequence in sequences:
    with open("tmp_job.pbs", "w") as f:
        f.write(
f"""#!/bin/bash
#PBS -N ensemble
#PBS -A UPRI0032
#PBS -q main
#PBS -m bae
#PBS -M benjaminwest@arizona.edu
#PBS -l walltime=12:00:00 
#PBS -l select=1:ncpus=64:mpiprocs=64
#PBS -j oe

module load conda
conda activate droughts
cd {project_root}/ensemble_running/pbs_outputs
source ~/pf_env.sh
python3 ../run_sequence_on_domain.py {domain_name} {sequence} {project_root} {ensemble_name} {TESTING}
        """)
    os.system(f"qsub tmp_job.pbs")
    shutil.rmtree(f"{project_root}/ensemble_running/pbs_outputs/tmp_job.pbs", ignore_errors=True)
