import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime

def scrape_bger():
    # 1. Die Seite mit den neu publizierten Entscheiden aufrufen
    url = "https://www.bger.ch/ext/eurospider/live/de/php/aza/http/index_aza.php?lang=de&mode=index"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        ergebnisse = []
        # 2. Alle Links auf der Seite finden
        for link in soup.find_all('a', href=True):
            text = link.get_text().strip()
            
            # 3. Prüfen, ob das Aktenzeichen mit 9C oder 8C beginnt (IV-relevant)
            if text.startswith("9C_") or text.startswith("8C_"):
                fall = {
                    "aktenzeichen": text,
                    "datum": datetime.now().strftime("%d.%m.%Y"),
                    "zusammenfassung": "Neues Urteil gefunden. Klicken für Details auf der BGer-Seite."
                }
                ergebnisse.append(fall)

        # 4. Falls keine IV-Urteile gefunden wurden, die Info-Meldung zeigen
        if not ergebnisse:
            ergebnisse = [{
                "aktenzeichen": "Info",
                "datum": datetime.now().strftime("%d.%m.%Y"),
                "zusammenfassung": "Heute wurden keine neuen IV-relevanten Urteile publiziert."
            }]
            
    except Exception as e:
        ergebnisse = [{
            "aktenzeichen": "Fehler",
            "datum": "Service",
            "zusammenfassung": f"Verbindung zum BGer fehlgeschlagen: {str(e)}"
        }]

    # 5. In die JSON-Datei schreiben, die deine App liest
    with open('urteile.json', 'w', encoding='utf-8') as f:
        json.dump(ergebnisse, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    scrape_bger()
