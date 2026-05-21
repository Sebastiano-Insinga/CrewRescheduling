#!/bin/bash
#SBATCH --job-name=python_test_job       # Name of the job
#SBATCH --partition=test
#SBATCH --output=output_%j.log 
#SBATCH --error=error_%j.log 


. ~/.bashrc
conda activate myenv
python Main.py



