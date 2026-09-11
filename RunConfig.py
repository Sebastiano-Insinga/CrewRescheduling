"""Risoluzione dei path di una run, da riga di comando.

Il problema che questo modulo esiste per togliere di mezzo: i tre file crew di
un'istanza (schedule, task, id mapping) hanno senso solo se vengono dalla stessa
conversione. Gli id dei task sono definiti dal .tsv che li ha generati, e
incrociare directory di run diverse non solleva nessuna eccezione: produce
numeri sbagliati in silenzio.

La difesa e' passare un token solo invece di tre path. --chain punta a una
cartella che contiene chain.json, e quel manifest dichiara le proprie tre
directory RELATIVE a se stesso. Le tre directory non le sceglie piu' chi lancia.

Istanze e network restano fuori dalla catena, perche' non ne fanno parte:
arrivano da --instance-dir, e network/shortest-paths si derivano da li' se non
vengono passati esplicitamente.
"""

import argparse
import json
import os

CHAIN_MANIFEST = "chain.json"

_CHAIN_KEYS = ("crew_schedule", "crew_task", "id_mapping")


class RunPaths:
    """I sei path di una run, gia' risolti e verificati."""

    def __init__(self, instance_dir, network, shortest_paths,
                 crew_schedule_dir, crew_task_dir, id_mapping_dir,
                 chain_dir=None, chain_name=None):
        self.instance_dir      = instance_dir
        self.network           = network
        self.shortest_paths    = shortest_paths
        self.crew_schedule_dir = crew_schedule_dir
        self.crew_task_dir     = crew_task_dir
        self.id_mapping_dir    = id_mapping_dir
        self.chain_dir         = chain_dir
        self.chain_name        = chain_name

    def as_run_info(self) -> dict:
        """Finisce dentro ogni output, cosi' un risultato dice da dove viene.

        Senza questo un risultato vecchio non e' distinguibile da uno nuovo se
        non ricostruendo la shell history, che e' esattamente il buco per cui
        una run va rifatta per scrupolo invece che per necessita'.
        """
        return {
            'chain':             self.chain_name or self.chain_dir,
            'instance_dir':      self.instance_dir,
            'crew_schedule_dir': self.crew_schedule_dir,
            'crew_task_dir':     self.crew_task_dir,
            'id_mapping_dir':    self.id_mapping_dir,
        }

    def apply_to(self, *modules) -> None:
        """Ribinda le globali dei moduli che leggono i path come tali.

        setup_instance() e run_instance() rileggono queste dal proprio modulo,
        quindi vanno impostate li'. Attenzione: un "from ... import NOME" ne
        crea una copia scollegata, fotografata al momento dell'import, che
        questa funzione non puo' raggiungere. Chi importa cosi' deve passare a
        "import IntegratedRescheduling as IR" e leggere IR.NOME sul punto d'uso.
        """
        for mod in modules:
            mod.INSTANCE_DIR       = self.instance_dir
            mod.NETWORK_FILE       = self.network
            mod.SHORTESTPATHS_FILE = self.shortest_paths
            mod.CREW_SCHEDULE_DIR  = self.crew_schedule_dir
            mod.CREW_TASK_DIR      = self.crew_task_dir
            mod.ID_MAPPING_DIR     = self.id_mapping_dir

    def __repr__(self):
        return (f"RunPaths(chain={self.chain_name!r}, "
                f"instance_dir={self.instance_dir!r})")


def load_chain(chain_dir: str) -> dict:
    """Legge chain.json e risolve le tre directory rispetto alla cartella."""
    manifest_path = os.path.join(chain_dir, CHAIN_MANIFEST)
    if not os.path.exists(manifest_path):
        raise FileNotFoundError(
            f"{manifest_path} non trovato: {chain_dir} non e' una catena crew. "
            f"Una catena e' una cartella con {CHAIN_MANIFEST} che dichiara "
            f"crew_schedule, crew_task e id_mapping relativi a se stessa.")

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    missing = [k for k in _CHAIN_KEYS if k not in manifest]
    if missing:
        raise KeyError(f"{manifest_path}: mancano le chiavi {missing}")

    resolved = {k: os.path.join(chain_dir, manifest[k]) for k in _CHAIN_KEYS}
    for key, path in resolved.items():
        if not os.path.isdir(path):
            raise NotADirectoryError(
                f"{manifest_path}: '{key}' punta a {path}, che non esiste")

    resolved['name'] = manifest.get('name', os.path.basename(os.path.normpath(chain_dir)))
    return resolved


def validate_chain(paths: RunPaths, instance_ids) -> list:
    """Verifica che schedule e mapping appartengano davvero alla stessa catena.

    Gli _sol.txt contengono id di task nudi. Se il mapping affiancato ha meno
    righe del massimo id citato, i due file vengono da conversioni diverse e
    ogni numero prodotto dalla run e' sbagliato. Il controllo costa una lettura
    di due file per istanza e trasforma un errore silenzioso in un crash
    all'avvio.

    Ritorna la lista dei problemi trovati, vuota se la catena e' coerente.
    """
    problems = []
    for iid in instance_ids:
        sched = os.path.join(paths.crew_schedule_dir, f"Transformed-{iid}_sol.txt")
        mapp  = os.path.join(paths.id_mapping_dir, f"ID-Mapping-Transformed-{iid}.tsv")

        if not os.path.exists(sched):
            problems.append(f"{iid}: manca {sched}")
            continue
        if not os.path.exists(mapp):
            problems.append(f"{iid}: manca {mapp}")
            continue

        max_task = 0
        with open(sched, "r", encoding="utf-8") as f:
            next(f, None)                      # intestazione Costs/Duration/Task_*
            for line in f:
                fields = line.split()
                if len(fields) <= 2:           # righe di coda, non sono duties
                    continue
                for tok in fields[2:]:
                    try:
                        max_task = max(max_task, int(tok))
                    except ValueError:
                        pass

        with open(mapp, "r", encoding="utf-8") as f:
            n_rows = sum(1 for _ in f)

        if max_task > n_rows:
            problems.append(
                f"{iid}: lo schedule cita il task {max_task} ma il mapping ha "
                f"{n_rows} righe. Schedule e mapping vengono da conversioni "
                f"diverse.")

    return problems


def add_path_args(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    """Aggiunge i flag di path. Nessun default: i percorsi non stanno nel codice."""
    g = parser.add_argument_group('percorsi della run')
    g.add_argument('--chain', default=None, dest='chain',
                   help='Cartella della catena crew, quella che contiene '
                        'chain.json (es. java/results0709). Da sola imposta '
                        'crew-schedule-dir, crew-task-dir e id-mapping-dir.')
    g.add_argument('--instance-dir', default=None, dest='instance_dir',
                   help='Directory delle istanze S*.json')
    g.add_argument('--network', default=None, dest='network',
                   help='network.json (default: dentro --instance-dir)')
    g.add_argument('--shortest-paths', default=None, dest='shortest_paths',
                   help='network-shortestpaths.json (default: dentro --instance-dir)')
    g.add_argument('--crew-schedule-dir', default=None, dest='crew_schedule_dir',
                   help='Directory dei Transformed-{id}_sol.txt. Scavalca --chain.')
    g.add_argument('--crew-task-dir', default=None, dest='crew_task_dir',
                   help='Directory dei Transformed-{id}.tsv. Scavalca --chain.')
    g.add_argument('--id-mapping-dir', default=None, dest='id_mapping_dir',
                   help='Directory degli ID-Mapping-Transformed-{id}.tsv. Scavalca --chain.')
    return parser


def resolve(args, parser: argparse.ArgumentParser = None) -> RunPaths:
    """Da args a RunPaths. Fallisce subito se qualcosa non e' stato passato."""

    def fail(msg):
        if parser is not None:
            parser.error(msg)
        raise ValueError(msg)

    if not args.instance_dir:
        fail("--instance-dir e' obbligatorio: i percorsi non hanno piu' un "
             "default nel codice.")
    if not os.path.isdir(args.instance_dir):
        fail(f"--instance-dir {args.instance_dir} non esiste")

    chain_dir  = args.chain
    chain_name = None
    crew_schedule = args.crew_schedule_dir
    crew_task     = args.crew_task_dir
    id_mapping    = args.id_mapping_dir

    if chain_dir:
        try:
            chain = load_chain(chain_dir)
        except (FileNotFoundError, KeyError, NotADirectoryError) as exc:
            fail(str(exc))
        chain_name    = chain['name']
        crew_schedule = crew_schedule or chain['crew_schedule']
        crew_task     = crew_task     or chain['crew_task']
        id_mapping    = id_mapping    or chain['id_mapping']

    unset = [name for name, value in (('--crew-schedule-dir', crew_schedule),
                                      ('--crew-task-dir', crew_task),
                                      ('--id-mapping-dir', id_mapping))
             if not value]
    if unset:
        fail(f"non risolti: {', '.join(unset)}. Passa --chain <cartella con "
             f"{CHAIN_MANIFEST}>, oppure i tre flag singolarmente.")

    network = args.network or os.path.join(args.instance_dir, "network.json")
    shortest = args.shortest_paths or os.path.join(args.instance_dir,
                                                   "network-shortestpaths.json")
    for label, path in (('network', network), ('shortest-paths', shortest)):
        if not os.path.exists(path):
            fail(f"{label}: {path} non esiste. Passalo esplicitamente con "
                 f"--{label} se non vive dentro --instance-dir.")

    return RunPaths(args.instance_dir, network, shortest,
                    crew_schedule, crew_task, id_mapping,
                    chain_dir=chain_dir, chain_name=chain_name)


def resolve_and_apply(args, modules, instance_ids=None,
                      parser: argparse.ArgumentParser = None) -> RunPaths:
    """Risolve, verifica la coerenza della catena, e ribinda le globali."""
    paths = resolve(args, parser)

    if instance_ids:
        problems = validate_chain(paths, instance_ids)
        if problems:
            msg = "catena crew incoerente:\n  " + "\n  ".join(problems)
            if parser is not None:
                parser.error(msg)
            raise ValueError(msg)

    paths.apply_to(*modules)
    return paths


def from_env(var_chain='CREW_CHAIN', var_instances='INSTANCE_DIR') -> RunPaths:
    """Variante per gli script senza argparse: stessi path, da variabili d'ambiente.

    Serve agli script diagnostici, che si lanciano a mano e non hanno una CLI.
    Fallisce con un messaggio che dice cosa esportare, invece di ripiegare su un
    default silenzioso.
    """
    chain_dir    = os.environ.get(var_chain)
    instance_dir = os.environ.get(var_instances)
    if not chain_dir or not instance_dir:
        raise RuntimeError(
            f"questo script legge i percorsi dall'ambiente. Esporta {var_chain} "
            f"(cartella con {CHAIN_MANIFEST}) e {var_instances} (directory delle "
            f"istanze) prima di lanciarlo, per esempio:\n"
            f"  {var_chain}=java/results0709 "
            f"{var_instances}=Instances/single_type/validation/single_type \\\n"
            f"      python3 <script>.py")

    ns = argparse.Namespace(
        chain=chain_dir, instance_dir=instance_dir, network=None,
        shortest_paths=None, crew_schedule_dir=None, crew_task_dir=None,
        id_mapping_dir=None,
    )
    return resolve(ns)
