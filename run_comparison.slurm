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
CHAIN=${3:-java/results0709}
INSTANCE_DIR=${4:-Instances/single_type/validation/single_type}
ID=$(printf "S%02d" $SLURM_ARRAY_TASK_ID)

cd $REPO

# I tre file della pipeline sono vincolati fra loro: gli id dei task valgono
# solo dentro la conversione che li ha prodotti, e un percorso sbagliato non
# solleva errori, produce numeri sbagliati (vedi java/PIPELINE.md). Per questo
# non si passano piu' tre directory separate ma --chain: le tre sottodirectory
# le dichiara chain.json, quindi non si possono piu' incrociare per sbaglio.
if [ ! -f "$CHAIN/chain.json" ]; then
    echo "ERRORE: $CHAIN non e' una catena crew, manca chain.json" >&2
    exit 1
fi
[ -f "$INSTANCE_DIR/$ID.json" ] || {
    echo "ERRORE: istanza mancante: $INSTANCE_DIR/$ID.json" >&2; exit 1; }

# La verifica di coerenza vera, che lo schedule non citi task assenti dal
# mapping, la fa RunConfig.validate_chain all'avvio del processo Python.

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
chain    : $CHAIN
instances: $INSTANCE_DIR
commit   : $COMMIT
job      : $SLURM_ARRAY_JOB_ID / task $SLURM_ARRAY_TASK_ID
node     : $SLURMD_NODENAME
started  : $(date -Is)
EOF

# -u: senza, lo stdout verso un file e' bufferizzato a blocchi e il log resta
# vuoto per minuti anche mentre il job avanza.
$PY -u Comparison_Integrated_Sequential/scripts/CompareSequentialIntegrated.py -i $ID -s $SEED \
    --chain "$CHAIN" \
    --instance-dir "$INSTANCE_DIR" \
    -o $RUNDIR/csv/$ID.csv \
    --export-solution $RUNDIR/solutions

# CompareSequentialIntegrated cattura le eccezioni dei due solver e le scrive in
# colonna invece di propagarle: senza questo controllo il task risulta OK anche
# con l'approccio integrato fallito, e la batch va avanti per ore producendo
# righe a meta'. Qui il task fallisce, cosi' squeue e sacct lo mostrano subito.
$PY -c "
import csv, sys
rows = list(csv.DictReader(open('$RUNDIR/csv/$ID.csv')))
bad  = [r for r in rows if r['error_sequential'] or r['error_integrated']]
for r in bad:
    print(f\"ERRORE {r['instance_id']}: seq={r['error_sequential']!r} int={r['error_integrated']!r}\",
          file=sys.stderr)
sys.exit(1 if bad else 0)
"
