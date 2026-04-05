import requests
import xml.etree.ElementTree as ET
import pandas as pd
# https://console.object.files.data.gouv.fr/browser/meteofrance/data%2Fvigilance%2Fmetropole%2F
BASE_URL = "https://console.object.files.data.gouv.fr"
PREFIX = "browser/meteofrance/data/vigilance/metropole/"

def list_files(prefix):
    url = f"{BASE_URL}/?list-type=2&prefix={prefix}"

    r = requests.get(url)
    root = ET.fromstring(r.content)

    files = []
    for content in root.findall("{http://s3.amazonaws.com/doc/2006-03-01/}Contents"):
        key = content.find("{http://s3.amazonaws.com/doc/2006-03-01/}Key").text
        files.append(key)

    return files


files = list_files(PREFIX)

# Filtrer les JSON "carte"
json_files = [f for f in files if f.endswith(".json")]

print(f"{len(json_files)} fichiers trouvés")

rows = []

for file in json_files:
    url = f"{BASE_URL}/{file}"

    try:
        r = requests.get(url)
        data = r.json()

        date = file.split("/")[4:7]
        date_str = "-".join(date)

        for dept in data["product"]["periods"][0]["timelaps"][0]["domain_ids"]:
            code = dept["domain_id"]

            for phenom in dept["phenomenon_items"]:
                if phenom["phenomenon_id"] == 2:
                    rows.append({
                        "date": date_str,
                        "departement": code,
                        "niveau": phenom["phenomenon_max_color_id"]
                    })

    except Exception as e:
        print("Erreur sur", file)

df = pd.DataFrame(rows)
df.to_csv("historique_canicule.csv", index=False)