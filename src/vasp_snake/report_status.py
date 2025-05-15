import json
import os

try:
    import yaml
except ImportError:
    yaml = None

from vasp_snake.force import parse_forces_and_check_zero

__all__ = ["classify_folders", "write_status_report"]


def classify_folders(root="."):
    status = {}
    for folder in sorted(os.listdir(root)):
        folder_path = os.path.join(root, folder)
        if not os.path.isdir(folder_path) or folder.startswith("."):
            continue
        outcar = os.path.join(folder_path, "OUTCAR")
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
    return status


def write_status_report(status_dict, filename, out_format="json"):
    if out_format == "json":
        with open(filename, "w") as f:
            json.dump(status_dict, f, indent=2)
    elif out_format == "yaml":
        if yaml is None:
            raise ImportError("pyyaml is required for YAML output.")
        with open(filename, "w") as f:
            yaml.dump(status_dict, f, sort_keys=False)
    else:
        raise ValueError("Unsupported format: {}".format(out_format))


# Optional: CLI interface
if __name__ == "__main__":
    import click

    @click.command()
    @click.option(
        "--format",
        "out_format",
        type=click.Choice(["json", "yaml"], case_sensitive=False),
        default="json",
        help="Output format (json or yaml)",
    )
    @click.option("--output", default=None, help="Output file name (optional)")
    @click.option("--folders", default=".", help="Root directory containing folders")
    def main(out_format, output, folders):
        status = classify_folders(folders)
        if output is None:
            output = f"vasp_status.{out_format}"
        write_status_report(status, output, out_format)

    main()
