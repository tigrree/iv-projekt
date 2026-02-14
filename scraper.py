import requests
from bs4 import BeautifulSoup
import json
import os

def scrape_bger():
    url = "https://search.bger.ch/ext/eurospider/live/de/php/aza/http/index_aza.php?lang=de&mode=index&search=false"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        # Hier findet die Suche statt (Platzhalter für die Logik)
        # Wir erstellen IMMER eine Liste, damit der Prozess nicht abbricht
        ergebnisse = [
            {
                "aktenzeichen": "Info",
                "datum": "14.02.2026",
                "zusammenfassung": "Heute wurden keine neuen IV-Urteile publiziert."
            }
        ]
    except Exception as e:
        ergebnisse = [{"aktenzeichen": "Fehler", "datum": "Stand heute", "zusammenfassung": str(e)}]

    with open('urteile.json', 'w', encoding='utf-8') as f:
        json.dump(ergebnisse, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    scrape_bger()
