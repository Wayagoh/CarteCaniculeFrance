"""
extract_canicule.py
--------------------
Parcourt l'arborescence vigilance_data/ et extrait pour chaque fichier
CDP_CARTE_EXTERNE.json les niveaux d'alerte canicule (phenomenon_id = "6")
par département, puis les écrit dans historique_canicule.csv.

Arborescence attendue :
    vigilance_data/
        {année}/
            {mois}/
                {jour}/
                    {timestamp}_CDP_CARTE_EXTERNE.json

Colonnes du CSV de sortie :
    date        → YYYY-MM-DD  (déduite de l'arborescence)
    departement → numéro de département (ex: 01, 2A, 2B, 75...)
    niveau      → phenomenon_max_color_id du phénomène canicule (1=vert,
                  2=jaune, 3=orange, 4=rouge)

Seules les lignes où phenomenon_id == "6" (canicule) sont conservées.
"""

import csv
import json
import logging
from pathlib import Path

# ─── LOGGING ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ─── CONFIGURATION ────────────────────────────────────────────────────────────
DATA_DIR    = Path("vigilance_data")          # dossier racine des JSON
OUTPUT_CSV  = Path("historique_canicule.csv") # fichier de sortie
PHENOMENON_CANICULE = "6"                     # canicule selon Météo-France

# ─── HELPERS ──────────────────────────────────────────────────────────────────

def normalize_dept(domain_id: str) -> str:
    """
    Normalise le numéro de département sur 2 caractères.
    Les domaines Météo-France sont codés sur 2 chiffres (ex: "01", "75")
    sauf la Corse qui utilise "2A" et "2B".
    Le domaine national "FRA" et les zones marines sont ignorés (retourne None).
    """
    # Domaines non-départementaux à ignorer
    NON_DEPT = {"FRA", "FRAN", "ATLA", "MANCHE", "MER_NORD"}
    if domain_id.upper() in NON_DEPT:
        return None
    # La Corse (2A / 2B) est déjà au bon format
    if domain_id.upper() in ("2A", "2B"):
        return domain_id.upper()
    # Domaines numériques : on vérifie que c'est bien un entier valide
    try:
        num = int(domain_id)
        # Départements métropolitains : 1-95, DOM : 971-976
        if 1 <= num <= 95 or 971 <= num <= 976:
            return f"{num:02d}"
    except ValueError:
        pass
    return None  # domaine inconnu → ignoré


def extract_from_file(json_path: Path, date_str: str) -> list[dict]:
    """
    Lit un fichier CDP_CARTE_EXTERNE.json et retourne la liste de dicts
    {date, departement, niveau} pour tous les départements ayant
    phenomenon_id == PHENOMENON_CANICULE.

    On prend la première période trouvée (échéance "J") pour la date
    considérée. Si plusieurs périodes existent pour le même jour,
    on conserve le niveau max sur l'ensemble des périodes.
    """
    try:
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("Impossible de lire %s : %s", json_path, exc)
        return []

    # Accumulation : dept → niveau max sur toutes les périodes
    dept_niveau: dict[str, int] = {}

    periods = data.get("product", {}).get("periods", [])
    for period in periods:
        domain_ids = period.get("timelaps", {}).get("domain_ids", [])
        for domain in domain_ids:
            dept = normalize_dept(str(domain.get("domain_id", "")))
            if dept is None:
                continue

            for pheno in domain.get("phenomenon_items", []):
                if str(pheno.get("phenomenon_id")) == PHENOMENON_CANICULE:
                    niveau = int(pheno.get("phenomenon_max_color_id", 1))
                    # On garde le maximum sur l'ensemble des périodes du fichier
                    dept_niveau[dept] = max(dept_niveau.get(dept, 0), niveau)

    return [
        {"date": date_str, "departement": dept, "niveau": niveau}
        for dept, niveau in dept_niveau.items()
    ]


# ─── CORE ─────────────────────────────────────────────────────────────────────

def build_csv(data_dir: Path, output_csv: Path) -> None:
    """
    Parcourt data_dir à la recherche de fichiers *_CDP_CARTE_EXTERNE.json
    et écrit les données canicule dans output_csv.
    """
    rows: list[dict] = []
    files_found = 0
    files_skipped = 0

    # Tri pour avoir un CSV chronologique
    json_files = sorted(data_dir.rglob("*_CDP_CARTE_EXTERNE.json"))

    if not json_files:
        log.error(
            "Aucun fichier *_CDP_CARTE_EXTERNE.json trouvé dans %s",
            data_dir.resolve(),
        )
        return

    for json_path in json_files:
        # Structure attendue :  .../année/mois/jour/timestamp_CDP_...json
        parts = json_path.parts
        try:
            # On remonte depuis le fichier : parts[-1]=fichier, [-2]=jour, [-3]=mois, [-4]=année
            jour  = parts[-2]
            mois  = parts[-3]
            annee = parts[-4]
            date_str = f"{annee}-{mois}-{jour}"
        except IndexError:
            log.warning("Structure inattendue pour %s, fichier ignoré", json_path)
            files_skipped += 1
            continue

        extracted = extract_from_file(json_path, date_str)
        if extracted:
            rows.extend(extracted)
            files_found += 1
        else:
            files_skipped += 1

    if not rows:
        log.warning("Aucune donnée canicule extraite.")
        return

    # Tri final : date puis département
    rows.sort(key=lambda r: (r["date"], r["departement"]))

    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "departement", "niveau"])
        writer.writeheader()
        writer.writerows(rows)

    log.info(
        "CSV écrit : %s  (%d lignes, %d fichiers traités, %d ignorés)",
        output_csv.resolve(),
        len(rows),
        files_found,
        files_skipped,
    )


# ─── ENTRY POINT ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    log.info("Extraction canicule depuis %s", DATA_DIR.resolve())
    build_csv(DATA_DIR, OUTPUT_CSV)