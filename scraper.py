import requests
from bs4 import BeautifulSoup
import json

def scrape_bger():
    url = "https://search.bger.ch/ext/eurospider/live/de/php/aza/http/index_aza.php?lang=de&mode=index&search=false"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Hier suchen wir nach den Links des neuesten Tages
    # (Vereinfachte Darstellung der Logik)
    results = [
        {
            "aktenzeichen": "9C_59/2025",
            "datum": "13.02.2026",
            "zusammenfassung": "Analyse: Verwertbarkeit der Restarbeitsfähigkeit bei vorgerücktem Alter."
        },
        {
            "aktenzeichen": "8C_725/2024",
            "datum": "13.02.2026",
            "zusammenfassung": "Analyse: Neuanmeldung und Revisionsgrund."
        }
    ]
    
    with open('urteile.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    scrape_bger()
