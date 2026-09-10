#!/bin/bash
#SBATCH --job-name=cmp
#SBATCH --partition=medium
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=16GB
#SBATCH --time=03:00:00
#SBATCH --array=1-20
#SBATCH --output=logs/cmp_%A_%a.log

# Uso:
#   sbatch run_comparison.slurm [RUNTAG] [SEED] [PIPELINE]
# RUNTAG  : nome della batch sotto Comparison_Integrated_Sequential/runs/
#           (default: id del job array)
# SEED    : seed passato a CompareSequentialIntegrated (default: 42)
# PIPELINE: radice della run di column generation (default: java/results0709)
#
# --time e' per task, non per l'array: ogni istanza ha le sue 3h. Il massimo
# osservato sull'approccio integrato e' 423 s, quindi il margine e' ampio.

# Init di Lmod: sul nodo di calcolo "module" non e' definito di suo.
if ! command -v module >/dev/null 2>&1; then
    source /etc/profile.d/lmod.sh 2>/dev/null \
        || source /opt/apps/2023-04-11_lmod.bash
fi
module use /opt/apps/modules/20102025

REPO=$SLURM_SUBMIT_DIR
VENV=$REPO/.venv-linux

# Il .venv committato nel repo e' macOS e qui non parte: serve quello Linux,
# creato a mano sul login node una volta sola.
if [ ! -x "$VENV/bin/python" ]; then
    echo "ERRORE: $VENV assente. Crealo sul login node:" >&2
    echo "  module load <python/X.Y>" >&2
    echo "  python3 -m venv .venv-linux" >&2
    echo "  .venv-linux/bin/pip install -r requirements-vns.txt" >&2
    exit 1
fi
PY=$VENV/bin/python

# Meglio fallire qui con un messaggio chiaro che a meta' istanza con un
# ModuleNotFoundError sepolto nel log. gurobipy serve installato ma senza
# licenza: la catena della comparazione non costruisce nessun modello.
$PY - <<'EOF' || exit 1
import importlib.util, sys
missing = [m for m in ('plotly','pandas','numpy','matplotlib','dash','gurobipy')
           if not importlib.util.find_spec(m)]
if missing:
    print(f"ERRORE: pacchetti mancanti nel venv: {missing}", file=sys.stderr)
    sys.exit(1)
EOF

RUNTAG=${1:-$SLURM_ARRAY_JOB_ID}
SEED=${2:-42}
PIPELINE=${3:-java/results0709}
ID=$(printf "S%02d" $SLURM_ARRAY_TASK_ID)

INSTANCE_DIR=Instances/single_type
CREW_SCHEDULE_DIR=$PIPELINE/results_twan_txt
CREW_TASK_DIR=$PIPELINE/mapping/Final_Rescheduled_Instances
ID_MAPPING_DIR=$PIPELINE/mapping/Final_Rescheduled_ID_Mappings

cd $REPO

# I tre file della pipeline sono vincolati fra loro: gli id dei task valgono
# solo dentro la conversione che li ha prodotti. Un percorso sbagliato non
# solleva errori, produce numeri sbagliati (vedi java/PIPELINE.md).
for f in "$INSTANCE_DIR/$ID.json" \
         "$CREW_SCHEDULE_DIR/Transformed-${ID}_sol.txt" \
         "$CREW_TASK_DIR/Transformed-${ID}.tsv" \
         "$ID_MAPPING_DIR/ID-Mapping-Transformed-${ID}.tsv"; do
    [ -f "$f" ] || { echo "ERRORE: file mancante: $f" >&2; exit 1; }
done

# Un CSV per task: export_to_csv apre in append, e 20 task sullo stesso file
# interlacciano le righe e riscrivono l'header. Il merge si fa a fine batch:
#   cd Comparison_Integrated_Sequential/runs/$RUNTAG/csv
#   head -1 S01.csv > ../$RUNTAG.csv && tail -q -n +2 S*.csv >> ../$RUNTAG.csv
RUNDIR=$REPO/Comparison_Integrated_Sequential/runs/$RUNTAG
mkdir -p $RUNDIR/csv

# Il commit serve a ricollegare i risultati alla versione del codice: con un
# array lungo e un git pull nel mezzo i task possono girare sorgenti diversi.
COMMIT=$(git -C "$REPO" rev-parse --short HEAD 2>/dev/null || echo sconosciuto)
cat > $RUNDIR/csv/${ID}_run_info.txt <<EOF
instance : $ID
seed     : $SEED
pipeline : $PIPELINE
commit   : $COMMIT
job      : $SLURM_ARRAY_JOB_ID / task $SLURM_ARRAY_TASK_ID
node     : $SLURMD_NODENAME
started  : $(date -Is)
EOF

$PY CompareSequentialIntegrated.py -i $ID -s $SEED \
    --instance-dir "$INSTANCE_DIR" \
    --crew-schedule-dir "$CREW_SCHEDULE_DIR" \
    --crew-task-dir "$CREW_TASK_DIR" \
    --id-mapping-dir "$ID_MAPPING_DIR" \
    -o $RUNDIR/csv/$ID.csv \
    --export-solution $RUNDIR/solutions
