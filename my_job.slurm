#!/bin/bash
#SBATCH --job-name=SequentialRescheduling
#SBATCH --partition=short
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --time=06:00:00
#SBATCH --output=logs/%x_%j.out
#SBATCH --error=logs/%x_%j.err

echo "Running job $SLURM_JOB_NAME with ID $SLURM_JOB_ID"
echo "Allocated nodes: $SLURM_JOB_NODELIST"

. /opt/apps/2023-04-11_lmod.bash
module purge ???

devo accedere ai nodi per caricare i programmi ? quali nodi ?
come carico il programma sul cluster


mkdir -p logs
python SequentialRescheduling.py
