#!/bin/bash
#SBATCH --job-name=colgen
#SBATCH --partition=medium
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=128GB
#SBATCH --time=12:00:00
#SBATCH --array=1-20
#SBATCH --output=logs/colgen_%A_%a.log

# Uso:
#   sbatch run_columngeneration.slurm [TSVDIR] [RUNTAG] [MIPGAP]
# TSVDIR: cartella dei TSV, relativa alla root del repo.
# RUNTAG: nome della cartella dei risultati sotto runs/.
# MIPGAP: gap di ottimalita' in fase 2 (0.01 = 1%). Default 0 = ottimo esatto.

# Init di Lmod: sul nodo di calcolo "module" non e' definito di suo.
if ! command -v module >/dev/null 2>&1; then
    source /etc/profile.d/lmod.sh 2>/dev/null \
        || source /opt/apps/2023-04-11_lmod.bash
fi
module use /opt/apps/modules/20102025

module load openjdk/17.0.11_9-none-none-hskcbib
module load cplex/cplex-studio-22.2

# Se i module non hanno funzionato il job deve fallire subito, non
# affidarsi all'ambiente ereditato dalla shell di submit.
command -v java >/dev/null || { echo "ERRORE: java non disponibile" >&2; exit 1; }

# Il module cplex non esporta CPLEX_HOME: la root e' quella dei path che
# prepende (vedi "module show cplex/cplex-studio-22.2").
CPLEX_ROOT=/opt/apps/CPLEX/CPLEX_Studio222
CPLEX_JAR=$CPLEX_ROOT/cplex/lib/cplex.jar
CPLEX_LIB=$CPLEX_ROOT/cplex/bin/x86-64_linux

REPO=$SLURM_SUBMIT_DIR
ID=$(printf "S%02d" $SLURM_ARRAY_TASK_ID)

# Cartella dei TSV convertiti, relativa alla root del repo (primo argomento).
TSVDIR=${1:-Final_Rescheduled_Instances}
TSV=$REPO/$TSVDIR/Transformed-$ID.tsv

if [ ! -f "$TSV" ]; then
    echo "ERRORE: istanza non trovata: $TSV" >&2
    exit 1
fi

# Etichetta della run (secondo argomento): identica per tutti i task
# dell'array, diversa a ogni sbatch, cosi' i risultati non si sovrascrivono
# tra submission. Default: id del job array.
RUNTAG=${2:-$SLURM_ARRAY_JOB_ID}

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

# Limite CPLEX sul MIP: 11h, un'ora sotto il walltime di 12h, cosi' se il
# limite scatta resta il tempo di esportare i CSV dei risultati.
MIPGAP=${3:-0}

# -Xmx e' 16 GB sotto --mem: CPLEX alloca fuori dall'heap Java (strutture
# native del solver), e un OOM kill di SLURM non lascia traccia nel log.
# Limite CPLEX sul MIP: 11h, un'ora sotto il walltime, cosi' se il limite
# scatta resta il tempo di esportare i CSV.
# mip.log accende il log del solver in fase 2: senza, il branch-and-bound
# e' completamente muto e non si vede il gap stringersi.
java -Xmx112g -Dmip.timelimit=39600 -Dmip.gap=$MIPGAP -Dmip.log=true \
     -Djava.library.path=$CPLEX_LIB -cp "$REPO/bin:$CPLEX_JAR" \
     scripts.Main "$TSV"
