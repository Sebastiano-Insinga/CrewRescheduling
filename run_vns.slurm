#!/bin/bash
#SBATCH --job-name=vns
#SBATCH --partition=medium
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=16GB
#SBATCH --time=06:00:00
#SBATCH --array=1-18
#SBATCH --output=logs/vns_%A_%a.log

# Uso:
#   sbatch run_vns.slurm [SHAKE] [KMAX] [RUNTAG]
# SHAKE : ordered | random          (default: random)
# KMAX  : ampiezza max del vicinato (default: 10)
# RUNTAG: nome della batch sotto VNS/runs/ (default: id del job array)
#
# --time e' per task: ogni istanza ha le sue 6h indipendenti, non 6h per
# l'array intero. Margine sulla peggiore storica (S15, 3h48 con k piu' bassi).

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
# ModuleNotFoundError sepolto nel log.
$PY - <<'EOF' || exit 1
import importlib.util, sys
missing = [m for m in ('plotly','pandas','numpy','matplotlib','dash','gurobipy')
           if not importlib.util.find_spec(m)]
if missing:
    print(f"ERRORE: pacchetti mancanti nel venv: {missing}", file=sys.stderr)
    sys.exit(1)
EOF

SHAKE=${1:-random}
KMAX=${2:-10}
RUNTAG=${3:-$SLURM_ARRAY_JOB_ID}
ID=$(printf "S%02d" $SLURM_ARRAY_TASK_ID)

INSTANCE=$REPO/Instances/single_type/$ID.json
if [ ! -f "$INSTANCE" ]; then
    echo "ERRORE: istanza non trovata: $INSTANCE" >&2
    exit 1
fi

# Il VNS gira sul set storico in results_twan_txt/, che arriva a S18: per questo
# l'array e' 1-18 e non 1-20. Il controllo serve comunque, perche' l'istanza
# JSON esiste anche per S19 e S20 e da sola non basta a far partire la catena.
CREW_SCHEDULE=$REPO/results_twan_txt/Transformed-${ID}_sol.txt
if [ ! -f "$CREW_SCHEDULE" ]; then
    echo "ERRORE: crew schedule mancante: $CREW_SCHEDULE" >&2
    exit 1
fi

# Un CSV per task: VNSExport apre in append (VNS/scripts/VNSExport.py), e 20
# task sullo stesso file interlacciano le righe e riscrivono l'header. Il
# merge si fa a fine batch:
#   cd VNS/runs/$RUNTAG/csv
#   head -1 S01.csv > ../$RUNTAG.csv && tail -q -n +2 S*.csv >> ../$RUNTAG.csv
RUNDIR=$REPO/VNS/runs/$RUNTAG
mkdir -p $RUNDIR/solutions $RUNDIR/csv
cd $REPO

# Il commit serve a ricollegare i risultati alla versione del codice: con un
# array lungo e un git pull nel mezzo i task possono girare sorgenti diversi.
COMMIT=$(git -C "$REPO" rev-parse --short HEAD 2>/dev/null || echo sconosciuto)
cat > $RUNDIR/csv/${ID}_run_info.txt <<EOF
instance : $ID
shake    : $SHAKE
k_max    : $KMAX
commit   : $COMMIT
job      : $SLURM_ARRAY_JOB_ID / task $SLURM_ARRAY_TASK_ID
node     : $SLURMD_NODENAME
started  : $(date -Is)
EOF

# --no-gantt: ogni task dell'array e' single-instance, quindi senza il flag
# scriverebbe un HTML plotly da diversi MB che sul cluster non apre nessuno.
$PY VNSRescheduler.py -i $ID -loop \
    --shake $SHAKE -k-max $KMAX --no-gantt \
    --export-solution $RUNDIR/solutions \
    -csv $RUNDIR/csv/$ID.csv
