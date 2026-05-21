import argparse
import json
from pathlib import Path
from typing import List, Tuple

from InstanceReader import read_instance_data
from RollingStockSolutionReader import readRollingStockSolution
from ShortestPathReader import read_shortest_path_data


def read_network_data_safe(file_path: Path) -> dict:
    with file_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    sections = {}
    for section in data.get("sections", []):
        section_id = section["id"]
        sections[section_id] = {
            "name": section["name"],
            "origin": section["origin"],
            "destination": section["destination"],
            "distance": section["distance"],
        }

    return {"sections": sections}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run RollingStockSolutionReader to generate transformed instance and ID mapping files."
    )

    parser.add_argument("--instance", help="Instance name without extension, e.g. 58-A-2290T-114L")
    parser.add_argument("--network", required=True, help="Path to network JSON file")
    parser.add_argument(
        "--instance-folder",
        help="Folder containing instance JSON files. If used with --solution-folder, all JSON files are processed.",
    )
    parser.add_argument("--shortest-path", required=True, help="Path to shortest-path JSON file")
    parser.add_argument("--solution", help="Path to a single rolling-stock solution SOL file")
    parser.add_argument(
        "--solution-folder",
        help="Folder containing rolling-stock solution .sol files. Matched by instance name.",
    )

    parser.add_argument("--train-speed", type=float, default=57.0, help="Train speed in km/h")
    parser.add_argument("--maintenance-time", type=float, default=10800.0, help="Maintenance time in seconds")
    parser.add_argument(
        "--display-time-format",
        type=int,
        default=3,
        help="1=epoch, 2=datetime string, 3=minutes from base day",
    )

    return parser.parse_args()


def assert_exists(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{label} not found: {path}")


def resolve_jobs(args: argparse.Namespace) -> List[Tuple[str, Path, Path]]:
    if args.instance_folder and not args.instance and not args.solution:
        instance_folder = Path(args.instance_folder)
        assert_exists(instance_folder, "Instance folder")

        solution_folder = Path(args.solution_folder) if args.solution_folder else None
        if solution_folder:
            assert_exists(solution_folder, "Solution folder")

        jobs = []
        skip_names = {"frisch-network", "frisch-network-shortestpaths", "network", "network-shortestpaths"}
        for instance_json_path in sorted(instance_folder.glob("*.json")):
            instance_name = instance_json_path.stem
            if instance_name in skip_names:
                continue
            if solution_folder:
                # Support both exact match and glob pattern (e.g. S01.json_*.sol)
                exact = solution_folder / f"{instance_name}.sol"
                if exact.exists():
                    solution_path = exact
                else:
                    matches = sorted(solution_folder.glob(f"{instance_name}.json_*.sol"))
                    if not matches:
                        print(f"WARNING: no solution file found for {instance_name}, skipping.")
                        continue
                    solution_path = matches[0]
            else:
                solution_path = None  # will be read from embedded instance JSON
            jobs.append((instance_name, instance_json_path, solution_path))

        if not jobs:
            raise FileNotFoundError(f"No JSON instance files found in {instance_folder}")

        return jobs

    if not args.instance:
        raise ValueError("--instance is required unless you use batch mode with --instance-folder")
    if not args.instance_folder:
        raise ValueError("--instance-folder is required to locate the instance JSON")

    instance_json_path = Path(args.instance_folder) / f"{args.instance}.json"
    solution_path = Path(args.solution) if args.solution else None
    return [(args.instance, instance_json_path, solution_path)]


def run_job(
    root: Path,
    instance_name: str,
    instance_json_path: Path,
    solution_path: Path,
    network_data: dict,
    shortest_path_matrix: dict,
    args: argparse.Namespace,
) -> None:
    assert_exists(instance_json_path, "Instance JSON")
    if solution_path is not None:
        assert_exists(solution_path, "Solution file")

    print(f"Processing instance: {instance_name}")

    if solution_path is None:
        with instance_json_path.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        if "solution" not in raw:
            raise KeyError(f"No 'solution' key in {instance_json_path} and no --solution provided")
        sol_arg = raw["solution"]
    else:
        sol_arg = str(solution_path)

    instance_data = read_instance_data(str(instance_json_path))

    readRollingStockSolution(instance_name, sol_arg, network_data, instance_data, shortest_path_matrix, args.train_speed, args.maintenance_time, args.display_time_format, False, "2018-09-10",)
    "verifica la presenza dei file necessari e poi esegue la trasformazione per un'istanza specifica"
    generated_rescheduled_tsv = root / "Final_Rescheduled_Instances" / f"Transformed-{instance_name}.tsv"
    generated_id_mapping_tsv = root / "Final_Rescheduled_ID_Mappings" / f"ID-Mapping-Transformed-{instance_name}.tsv"

    print(f"Generated instance: {generated_rescheduled_tsv}")
    print(f"Generated ID mapping: {generated_id_mapping_tsv}")


def main() -> None:
    args = parse_args()
    root = Path(__file__).resolve().parent

    network_path = Path(args.network)
    shortest_path_path = Path(args.shortest_path)

    assert_exists(network_path, "Network file")
    assert_exists(shortest_path_path, "Shortest-path JSON")

    print("[1/2] Reading shared input data...")
    network_data = read_network_data_safe(network_path)
    shortest_path_matrix = read_shortest_path_data(str(shortest_path_path))
    jobs = resolve_jobs(args)

    print(f"[2/2] Running RollingStockSolutionReader for {len(jobs)} instance(s)...")
    for instance_name, instance_json_path, solution_path in jobs:
        run_job(
            root,
            instance_name,
            instance_json_path,
            solution_path,
            network_data,
            shortest_path_matrix,
            args,
        )

    print("Done.")


if __name__ == "__main__":
    main()
