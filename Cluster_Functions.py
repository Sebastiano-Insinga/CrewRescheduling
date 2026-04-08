import os

def generate_slurm_files(original_slurm_file, output_folder, instances):
    """
    Generates one Slurm script per instance.

    :param original_slurm_file: path to the original Slurm script
    :param output_folder: folder to store generated Slurm scripts
    :param instances: list of instance names
    """
    os.makedirs(output_folder, exist_ok=True)

    # Read original Slurm script
    with open(original_slurm_file, "r") as f:
        slurm_lines = f.readlines()

    for instance in instances:
        new_lines = []
        for line in slurm_lines:
            if line.strip().startswith("python Main.py"):
                # Replace with instance-specific command
                new_lines.append(f"python Main.py {instance}\n")
            elif line.strip().startswith("#SBATCH --job-name="):
                # Update job name
                new_lines.append(f"#SBATCH --job-name=python_{instance}\n")
            elif line.strip().startswith("#SBATCH --output="):
                # Update output log
                new_lines.append(f"#SBATCH --output=output_{instance}_%j.log\n")
            elif line.strip().startswith("#SBATCH --error="):
                # Update error log
                new_lines.append(f"#SBATCH --error=error_{instance}_%j.log\n")
            else:
                new_lines.append(line)

        # Write new Slurm file
        output_file = os.path.join(output_folder, f"slurm_{instance}.sh")
        with open(output_file, "w") as f_out:
            f_out.writelines(new_lines)

        print(f"Generated {output_file}")

def generate_master_slurm(slurm_folder, master_file="submit_all_instances.sh"):
    """
    Generates a master Slurm script that submits all individual Slurm jobs in slurm_folder.

    :param slurm_folder: folder containing the individual Slurm scripts
    :param master_file: path to save the master submission script
    """
    slurm_scripts = [
        f for f in os.listdir(slurm_folder)
        if f.endswith(".sh") and os.path.isfile(os.path.join(slurm_folder, f))
    ]
    slurm_scripts.sort()  # optional, to submit in alphabetical order

    with open(master_file, "w") as f:
        f.write("#!/bin/bash\n\n")
        for script in slurm_scripts:
            f.write(f"sbatch {os.path.join(slurm_folder, script)}\n")

    os.chmod(master_file, 0o755)
    print(f"Master Slurm submission script created: {master_file}")

def fix_slurm_files(slurm_folder):
    """
    Fixes all .sh files in the folder by:
    1. Converting DOS line endings (\r\n) to UNIX (\n)
    2. Replacing '#SBATCH --partition=test' with '#SBATCH --partition=short'
    """
    for fname in os.listdir(slurm_folder):
        if fname.endswith(".sh"):
            full_path = os.path.join(slurm_folder, fname)

            # Read raw bytes
            with open(full_path, "rb") as f:
                content = f.read()

            # Fix line endings: CRLF → LF
            fixed = content.replace(b"\r\n", b"\n").replace(b"\r", b"\n")

            # Replace partition line
            fixed = fixed.replace(
                b"#SBATCH --partition=test",
                b"#SBATCH --partition=short"
            )

            # Write back corrected content
            with open(full_path, "wb") as f:
                f.write(fixed)

            print(f"Updated: {full_path}")