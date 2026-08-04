import argparse
import os


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run steady-state spinup for a domain (repeat forcing year)."
    )
    parser.add_argument(
        "domain_name",
        help="Domain folder name under domains/ (e.g. potomac_flow_barrier_002)",
    )
    args = parser.parse_args()

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    base_dir = os.path.join(
        project_root, "domains", args.domain_name, "spinup", "run"
    )
    run_yaml = os.path.join(base_dir, "run.yaml")

    if not os.path.isfile(run_yaml):
        raise FileNotFoundError(f"Run definition not found: {run_yaml}")

    import parflow as pf

    os.chdir(base_dir)
    run = pf.Run.from_definition(run_yaml)
    run.write("run", file_format="yaml")
    # YAML from hydrodata/subset uses _value_ keys that ParFlow accepts but
    # parflow-tools validation does not fully describe.
    run.run(skip_validation=True)


if __name__ == "__main__":
    main()
