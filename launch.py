import threading
import webbrowser
from main import app

def open_browser():
    webbrowser.open("http://127.0.0.1:8050")

if __name__ == "__main__":
    threading.Timer(1.5, open_browser).start()
    app.run(debug=False, port=8050)

""" Commande pour créer l'exécutable: pyinstaller --onefile --noconsole --add-data "departements.geojson;." --add-data "RécuperationDonnées/historique_canicule.csv;RécuperationDonnées" launch.py"""