import json
import os

import click

try:
    import yaml
except ImportError:
    yaml = None

from .force import parse_forces_and_check_zero


@click.command()
@click.option(
    "--format",
    "out_format",
    type=click.Choice(["json", "yaml"], case_sensitive=False),
    default="json",
    help="Output format (json or yaml)",
)
@click.option("--folders", default=".", help="Root directory containing folders")
def main(out_format, folders):
    status = {}
    folders_list = [
        d
        for d in os.listdir(folders)
        if os.path.isdir(os.path.join(folders, d)) and not d.startswith(".")
    ]
    for folder in sorted(folders_list):
        outcar = os.path.join(folders, folder, "OUTCAR")
        if not os.path.exists(outcar):
            status[folder] = {"status": "not_run", "reason": "OUTCAR missing"}
        else:
            forces_sum, close = parse_forces_and_check_zero(outcar)
            if close is None:
                status[folder] = {
                    "status": "not_converged",
                    "reason": "No force block found",
                }
            elif close:
                status[folder] = {
                    "status": "done",
                    "forces_sum": [float(f) for f in forces_sum],
                }
            else:
                status[folder] = {
                    "status": "not_converged",
                    "forces_sum": [float(f) for f in forces_sum],
                }

    if out_format == "json":
        print(json.dumps(status, indent=2))
    elif out_format == "yaml":
        if yaml is None:
            print("pyyaml not installed. Please install pyyaml.")
            exit(1)
        print(yaml.dump(status, sort_keys=False))


if __name__ == "__main__":
    main()
