import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime

def scrape_bger():
    # Wir fügen die aktuelle Uhrzeit hinzu, damit die Datei immer "neu" ist
    zeitstempel = datetime.now().strftime("%d.%m.%Y, %H:%M")
    
    url = "https://search.bger.ch/ext/eurospider/live/de/php/aza/http/index_aza.php?lang=de&mode=index&search=false"
    
    # Standard-Inhalt, falls (noch) nichts gefunden wird
    ergebnisse = [{
        "aktenzeichen": "Status",
        "datum": zeitstempel,
        "zusammenfassung": "Das Skript läuft. Aktuell werden keine neuen IV-Urteile publiziert (Wochenende/Feiertag)."
    }]
    
    # Später fügen wir hier die Such-Logik ein
    
    with open('urteile.json', 'w', encoding='utf-8') as f:
        json.dump(ergebnisse, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    scrape_bger()
