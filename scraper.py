import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime

def scrape_bger():
    base_url = "https://www.bger.ch/ext/eurospider/live/de/php/aza/http/index_aza.php?lang=de&mode=index"
    domain = "https://www.bger.ch"
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
    
    alle_entscheide = []
    heute = datetime.now()
    heute_str = heute.strftime("%d.%m.%Y")
    wochentag = heute.weekday() # 0=Montag, 5=Samstag, 6=Sonntag

    try:
        response = requests.get(base_url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 1. Alle Datums-Links der letzten 14 Tage finden
        date_links = []
        for a in soup.find_all('a', href=True):
            if a.get_text().strip().count('.') == 2:
                date_links.append((a.get_text().strip(), a['href']))

        gefunden_fuer_heute = False

        # 2. Die Tage durchgehen
        for datum, link in date_links:
            day_url = link if link.startswith("http") else domain + link
            day_res = requests.get(day_url, headers=headers, timeout=10)
            day_soup = BeautifulSoup(day_res.text, 'html.parser')
            
            for case_link in day_soup.find_all('a', href=True):
                case_text = case_link.get_text().strip()
                if case_text.startswith("9C_") or case_text.startswith("8C_"):
                    alle_entscheide.append({
                        "aktenzeichen": case_text,
                        "datum": datum,
                        "zusammenfassung": f"IV-Urteil vom {datum}. Klicken für Details.",
                        "url": case_link['href'] if case_link['href'].startswith("http") else domain + case_link['href']
                    })
                    if datum == heute_str:
                        gefunden_fuer_heute = True

        # 3. Info-Eintrag NUR an Wochentagen (Mo-Fr), wenn nichts gefunden wurde
        if not gefunden_fuer_heute and wochentag < 5:
            alle_entscheide.insert(0, {
                "aktenzeichen": "Info",
                "datum": heute_str,
                "zusammenfassung": "Heute wurden keine neuen IV-relevanten Urteile publiziert.",
                "url": None
            })

    except Exception as e:
        alle_entscheide = [{"aktenzeichen": "Fehler", "datum": heute_str, "zusammenfassung": str(e), "url": None}]

    # 4. Speichern der urteile.json
    with open('urteile.json', 'w', encoding='utf-8') as f:
        json.dump(alle_entscheide, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    scrape_bger()
