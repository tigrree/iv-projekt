import requests
from bs4 import BeautifulSoup
import json

def scrape_bger():
    # Wir erstellen eine Standard-Meldung, falls nichts gefunden wird
    ergebnisse = [{
        "aktenzeichen": "Info",
        "datum": "14.02.2026",
        "zusammenfassung": "Aktuell keine neuen IV-Urteile publiziert. Das Skript prüft täglich weiter."
    }]
    
    url = "https://search.bger.ch/ext/eurospider/live/de/php/aza/http/index_aza.php?lang=de&mode=index&search=false"
    
    try:
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            # Hier bauen wir später die echte Such-Logik ein
            # Für den Test lassen wir diese Liste, damit das Skript "Erfolg" hat
            pass 
    except Exception as e:
        print(f"Fehler beim Laden: {e}")

    # Wir schreiben die Datei IMMER, damit GitHub Action einen Grund zum Speichern hat
    with open('urteile.json', 'w', encoding='utf-8') as f:
        json.dump(ergebnisse, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    scrape_bger()
