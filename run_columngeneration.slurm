#!/bin/bash
#SBATCH --job-name=colgen
#SBATCH --partition=medium
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=32GB
#SBATCH --time=12:00:00
#SBATCH --array=1-20
#SBATCH --output=logs/colgen_%A_%a.log

. ~/.bash_profile
. /opt/apps/2023-04-11_lmod.bash
module load java
module load cplex

CPLEX_JAR=$CPLEX_HOME/cplex/lib/cplex.jar
CPLEX_LIB=$CPLEX_HOME/cplex/bin/x86-64_linux

REPO=$SLURM_SUBMIT_DIR
ID=$(printf "S%02d" $SLURM_ARRAY_TASK_ID)

# Cartella dei TSV convertiti. Sovrascrivibile al lancio per usare una
# conversione specifica, es.:
#   sbatch --export=ALL,TSVDIR=conversions/20260907_1530/Final_Rescheduled_Instances \
#          run_columngeneration.slurm
TSVDIR=${TSVDIR:-Final_Rescheduled_Instances}
TSV=$REPO/$TSVDIR/Transformed-$ID.tsv

if [ ! -f "$TSV" ]; then
    echo "ERRORE: istanza non trovata: $TSV" >&2
    exit 1
fi

# Etichetta della run: identica per tutti i task dell'array, diversa a ogni
# sbatch, cosi' i risultati non si sovrascrivono tra submission.
# Per un nome parlante: sbatch --export=ALL,RUNTAG=scored_greedy ...
RUNTAG=${RUNTAG:-$SLURM_ARRAY_JOB_ID}

# results/ e' relativo alla CWD: una dir per istanza, niente collisioni tra task.
RUNDIR=$REPO/runs/$RUNTAG/$ID
mkdir -p $RUNDIR/results
cd $RUNDIR

# Traccia da dove viene l'input di questa run.
cat > run_info.txt <<EOF
instance : $ID
tsv      : $TSV
job      : $SLURM_ARRAY_JOB_ID / task $SLURM_ARRAY_TASK_ID
node     : $SLURMD_NODENAME
started  : $(date -Is)
EOF

java -Xmx28g -Djava.library.path=$CPLEX_LIB -cp "$REPO/bin:$CPLEX_JAR" \
     scripts.Main "$TSV"
