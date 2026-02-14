import requests
from bs4 import BeautifulSoup
import json
import os
import time
from datetime import datetime

# API Key von Groq
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

def summarize_with_ai(urteil_text):
    if not GROQ_API_KEY:
        return "Vorschau: Details im Originalurteil verfügbar."
    
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    prompt = f"""Du bist ein spezialisierter Jurist für Schweizer Sozialversicherungsrecht. 
    Fasse das folgende Urteil zur Invalidenversicherung (IV) in maximal 3-4 Sätzen zusammen.
    Konzentriere dich auf: 1. Sachverhalt, 2. Die entscheidende Rechtsfrage, 3. Das Ergebnis (Gutgeheissen/Abgewiesen).
    
    Text des Urteils:
    {urteil_text[:4000]}"""

    data = {
        "model": "llama3-8b-8192",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=15)
        return response.json()['choices'][0]['message']['content'].strip()
    except Exception as e:
        print(f"KI Fehler: {e}")
        return "Zusammenfassung konnte nicht generiert werden."

def scrape_bger():
    base_url = "https://www.bger.ch/ext/eurospider/live/de/php/aza/http/index_aza.php?lang=de&mode=index"
    domain = "https://www.bger.ch"
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
    
    heute_str = datetime.now().strftime("%d.%m.%Y")
    wochentag = datetime.now().weekday()
    
    # --- 1. SCHRITT: Vorhandene Daten laden (Gedächtnis) ---
    alte_daten = []
    if os.path.exists('urteile.json'):
        try:
            with open('urteile.json', 'r', encoding='utf-8') as f:
                alte_daten = json.load(f)
        except:
            alte_daten = []
    
    # Erstelle ein Dictionary für schnellen Zugriff (Aktenzeichen -> Zusammenfassung)
    archiv = {d['aktenzeichen']: d['zusammenfassung'] for d in alte_daten if d['aktenzeichen'] != "Info"}
    
    neue_liste = []
    gefunden_fuer_heute = False

    try:
        response = requests.get(base_url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        date_links = [(a.get_text().strip(), a['href']) for a in soup.find_all('a', href=True) if a.get_text().strip().count('.') == 2]

        # Wir prüfen nur die Tage, die das BGer aktuell anzeigt
        for datum, link in date_links:
            day_url = link if link.startswith("http") else domain + link
            day_res = requests.get(day_url, headers=headers, timeout=10)
            day_soup = BeautifulSoup(day_res.text, 'html.parser')
            
            for case_link in day_soup.find_all('a', href=True):
                az = case_link.get_text().strip()
                if az.startswith("9C_") or az.startswith("8C_"):
                    full_link = case_link['href'] if case_link['href'].startswith("http") else domain + case_link['href']
                    
                    # --- 2. SCHRITT: Prüfen, ob wir dieses Urteil schon kennen ---
                    if az in archiv:
                        zusammenfassung = archiv[az]
                        print(f"Bekanntes Urteil: {az} - Kopiere Zusammenfassung.")
                    else:
                        print(f"NEUES Urteil: {az} - Befrage KI...")
                        try:
                            case_page = requests.get(full_link, headers=headers, timeout=10)
                            case_content = BeautifulSoup(case_page.text, 'html.parser').get_text()
                            zusammenfassung = summarize_with_ai(case_content)
                            time.sleep(2) # Kurze Pause für die API
                        except:
                            zusammenfassung = "Details im Originalurteil verfügbar."

                    neue_liste.append({
                        "aktenzeichen": az,
                        "datum": datum,
                        "zusammenfassung": zusammenfassung,
                        "url": full_link
                    })
                    if datum == heute_str:
                        gefunden_fuer_heute = True

        # Info-Meldung für heute, falls Werktag und keine Urteile
        if not gefunden_fuer_heute and wochentag < 5:
            neue_liste.insert(0, {
                "aktenzeichen": "Info",
                "datum": heute_str,
                "zusammenfassung": "Heute wurden keine neuen IV-relevanten Urteile publiziert.",
                "url": None
            })

    except Exception as e:
        print(f"Fehler im Scraper: {e}")

    # --- 3. SCHRITT: Speichern ---
    with open('urteile.json', 'w', encoding='utf-8') as f:
        json.dump(neue_liste, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    scrape_bger()
