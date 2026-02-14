import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime

def scrape_bger():
    base_url = "https://www.bger.ch/ext/eurospider/live/de/php/aza/http/index_aza.php?lang=de&mode=index"
    domain = "https://www.bger.ch"
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
    
    alle_entscheide = []
    heute_str = datetime.now().strftime("%d.%m.%Y")
    gefunden_fuer_heute = False

    try:
        # 1. Hauptseite laden (Liste der letzten 14 Tage)
        response = requests.get(base_url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 2. Alle Datums-Links finden (z.B. "13.02.2026")
        date_links = []
        for a in soup.find_all('a', href=True):
            if a.get_text().strip().count('.') == 2: # Einfacher Check für Datumsformat
                date_links.append((a.get_text().strip(), a['href']))

        # 3. Jeden Tag einzeln prüfen
        for datum, link in date_links:
            day_url = link if link.startswith("http") else domain + link
            day_res = requests.get(day_url, headers=headers, timeout=10)
            day_soup = BeautifulSoup(day_res.text, 'html.parser')
            
            tag_funde = 0
            for case_link in day_soup.find_all('a', href=True):
                case_text = case_link.get_text().strip()
                if case_text.startswith("9C_") or case_text.startswith("8C_"):
                    href = case_link['href']
                    full_link = href if href.startswith("http") else domain + href
                    
                    alle_entscheide.append({
                        "aktenzeichen": case_text,
                        "datum": datum,
                        "zusammenfassung": f"IV-Urteil vom {datum}. Klicken für Details.",
                        "url": full_link
                    })
                    tag_funde += 1
                    if datum == heute_str:
                        gefunden_fuer_heute = True

        # 4. Spezialfall für heute hinzufügen, wenn nichts gefunden wurde
        if not gefunden_fuer_heute:
            alle_entscheide.insert(0, {
                "aktenzeichen": "Info",
                "datum": heute_str,
                "zusammenfassung": "Heute wurden keine neuen IV-relevanten Urteile publiziert.",
                "url": None
            })

    except Exception as e:
        alle_entscheide = [{"aktenzeichen": "Fehler", "datum": heute_str, "zusammenfassung": str(e), "url": None}]

    # 5. Speichern
    with open('urteile.json', 'w', encoding='utf-8') as f:
        json.dump(alle_entscheide, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    scrape_bger()
