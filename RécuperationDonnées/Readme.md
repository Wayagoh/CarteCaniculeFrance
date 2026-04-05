# vigilance-download

Download Météo-France weather vigilance data for metropolitan France, from the open data bucket hosted on data.gouv.fr.

---

## What it does

For each day in the configured date range, the script picks the **last emission of the day** (final state of the vigilance) and downloads the selected JSON file(s) to a local folder.

---

## Data source

| Item | Detail |
|---|---|
| Provider | Météo-France |
| Bucket | `https://object.files.data.gouv.fr/meteofrance/data/vigilance/metropole/` |
| License | Licence Ouverte Etalab — free reuse, credit: *Météo-France* |
| Coverage | Metropolitan France, from November 2022 onwards |

---

## Bucket structure

```
metropole/
└── {YYYY}/
    └── {MM}/
        └── {DD}/
            └── {HHMMSS}/          ← emission timestamp (UTC)
                ├── CDP_CARTE_EXTERNE.json
                ├── CDP_TEXTES_VIGILANCE.json
                ├── CARTE_NATIONAL_J_J1.pdf
                ├── VIGNETTE_NATIONAL_J_500X500.png
                └── VIGNETTE_NATIONAL_J1_500X500.png
```

### Why multiple emissions per day?

Météo-France publishes an update every time the vigilance status changes. On a quiet day there are typically 2–3 emissions (morning and afternoon). During a weather crisis there can be 70+. The script keeps only the **last one** — the most up-to-date snapshot for that day.

### Target files

| File | Content |
|---|---|
| `CDP_CARTE_EXTERNE.json` | Vigilance levels (green/yellow/orange/red) per department, per phenomenon, with timeline |
| `CDP_TEXTES_VIGILANCE.json` | Written bulletins from meteorologists (national, zonal, departmental). Present in ~70% of emissions only. |

---

## Output structure

```
vigilance_data/
└── 2023/
    └── 01/
        └── 15/
            └── 150032_CDP_CARTE_EXTERNE.json
```

The filename prefix is the emission timestamp (`HHMMSS`) of the last emission of that day.

---

## Requirements

Python 3.10+ and the `requests` library:

```bash
pip install requests
```

---

## Sample output

```
10:02:14  INFO     Starting download — 2023-01-01 → 2025-12-31
10:02:14  INFO     Output directory : /home/user/vigilance_data
10:02:15  INFO     ok    2023-01-01  150032  [CDP_CARTE_EXTERNE.json]
10:02:15  INFO     ok    2023-01-02  150044  [CDP_CARTE_EXTERNE.json]
...
10:18:41  INFO     Done — 1056 downloaded, 0 skipped, 12 missing, 0 errors
```

`missing` means no emission with that file existed for that day (normal for `CDP_TEXTES_VIGILANCE.json`).

---

## Next step

Once downloaded, the JSON files can be parsed with pandas to build a daily recap per department and phenomenon.

---

*Source: Météo-France — Licence Ouverte Etalab*