import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime

def scrape_bger():
    # Basis-URL für die Verlinkung
    base_url = "https://www.bger.ch"
    url = "https://www.bger.ch/ext/eurospider/live/de/php/aza/http/index_aza.php?lang=de&mode=index"
    
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        ergebnisse = []

        for link in soup.find_all('a', href=True):
            text = link.get_text().strip()
            # Wir suchen nach 9C und 8C (Sozialversicherungsabteilungen)
            if text.startswith("9C_") or text.startswith("8C_"):
                href = link['href']
                # Wir bauen den vollständigen Link zusammen
                full_link = href if href.startswith("http") else base_url + href
                
                ergebnisse.append({
                    "aktenzeichen": text,
                    "datum": datetime.now().strftime("%d.%m.%Y"),
                    "zusammenfassung": "Neues IV-Urteil publiziert. Klicken Sie unten, um das Original auf der BGer-Seite zu lesen.",
                    "url": full_link  # Das ist das neue Feld!
                })

        if not ergebnisse:
            ergebnisse = [{
                "aktenzeichen": "Info",
                "datum": datetime.now().strftime("%d.%m.%Y"),
                "zusammenfassung": "Heute wurden keine neuen IV-relevanten Urteile publiziert.",
                "url": "https://www.bger.ch"
            }]
            
    except Exception as e:
        ergebnisse = [{"aktenzeichen": "Fehler", "datum": "Info", "zusammenfassung": str(e), "url": ""}]

    with open('urteile.json', 'w', encoding='utf-8') as f:
        json.dump(ergebnisse, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    scrape_bger()
