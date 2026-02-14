import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime

def scrape_bger():
    # Aktueller Zeitstempel
    zeitstempel = datetime.now().strftime("%d.%m.%Y, %H:%M")
    
    # Hier ändern wir deine Meldung
    ergebnisse = [{
        "aktenzeichen": "Info",
        "datum": zeitstempel,
        "zusammenfassung": "Heute wurden keine neuen IV-relevanten Urteile publiziert."
    }]
    
    # (Deine restliche Such-Logik bleibt hier...)
    
    with open('urteile.json', 'w', encoding='utf-8') as f:
        json.dump(ergebnisse, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    scrape_bger()
