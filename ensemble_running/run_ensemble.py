import argparse
import json
import os
import sys

from config import TESTING

project_root_default = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root_default not in sys.path:
    sys.path.insert(0, project_root_default)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Submit PBS jobs to run all sequences in an ensemble folder on one or more domains.",
    )
    parser.add_argument(
        "ensemble_name",
        help="Ensemble folder under run_sequences/ (e.g. droughts, 40_year_spinup)",
    )
    parser.add_argument(
        "domains",
        nargs="+",
        help="Domain folder name(s) under domains/ (e.g. wolf2 potomac2)",
    )
    parser.add_argument(
        "--project-root",
        default=project_root_default,
        help=f"Project root (default: {project_root_default})",
    )
    parser.add_argument(
        "--walltime",
        default="12:00:00",
        help="PBS walltime (default: 12:00:00)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print jobs that would be submitted without calling qsub",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    project_root = os.path.abspath(args.project_root)
    sequences_folder = os.path.join(project_root, "run_sequences", args.ensemble_name)

    if not os.path.isdir(sequences_folder):
        raise FileNotFoundError(f"Sequences folder not found: {sequences_folder}")

    sequences = sorted(
        os.path.join(sequences_folder, name)
        for name in os.listdir(sequences_folder)
        if name.endswith(".json")
    )
    if not sequences:
        raise FileNotFoundError(f"No .json sequences in {sequences_folder}")

    script_dir = os.path.dirname(os.path.abspath(__file__))
    job_script = os.path.join(script_dir, "tmp_job.pbs")

    for domain_name in args.domains:
        for sequence in sequences:
            with open(sequence) as f:
                sequence_data = json.load(f)
            sequence_name = sequence_data["name"]
            job_name = f"{domain_name}_{args.ensemble_name}_{sequence_name}"
            pbs = f"""#!/bin/bash
#PBS -N {job_name}
#PBS -A UPRI0032
#PBS -q main
#PBS -m bae
#PBS -M benjaminwest@arizona.edu
#PBS -l walltime={args.walltime}
#PBS -l select=4:ncpus=64:mpiprocs=64
#PBS -j oe
module load conda
conda activate droughts
cd {project_root}/ensemble_running/pbs_outputs
source ~/pf_env.sh
python3 ../run_sequence_on_domain.py {domain_name} {sequence} {project_root} {args.ensemble_name} {TESTING}
"""
            if args.dry_run:
                print(f"would submit: {job_name}")
                print(f"  sequence: {sequence}")
                continue

            with open(job_script, "w") as f:
                f.write(pbs)
            os.system(f"qsub {job_script}")


if __name__ == "__main__":
    main()
