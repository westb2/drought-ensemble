import argparse
import os
import sys

from config import TESTING

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


def main():
    parser = argparse.ArgumentParser(description="Download and prepare a ParFlow domain.")
    parser.add_argument("domain_name", help="Domain folder name under domains/ (e.g. potomac)")
    args = parser.parse_args()

    from classes.Domain import Domain

    domain = Domain(
        config_file=f"{project_root}/domains/{args.domain_name}/config.ini",
        project_root=project_root,
        TESTING=TESTING,
    )
    domain.get_domain()


if __name__ == "__main__":
    main()
