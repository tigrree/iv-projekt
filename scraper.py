import requests
from bs4 import BeautifulSoup
import json
import os
import time
from datetime import datetime

# --- DEINE MANUELLE EINSTELLUNG ---
ZIEL_DATUM = "11.02.2026"
# ----------------------------------

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

KEYWORDS = [
    "invalidenversicherung", 
    "invalidenrente", 
    "assurance-invalidité", 
    "rente d'invalidité", 
    "assicurazione per l’invalidità", 
    "rendita d'invalidità",
    "iv-stelle",
    "office ai",
    "ufficio ai"
]

def summarize_with_ai(urteil_text):
    if not GROQ_API_KEY: 
        return "API Key fehlt."
    clean_text = " ".join(urteil_text.split()[:750])
    PROMPT_TEXT = "Fasse das Urteil als Schweizer Jurist zusammen: **Sachverhalt & Anträge**, **Streitig**, **Zu prüfen & Entscheidung**. Zwingend Deutsch."
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": PROMPT_TEXT + clean_text}],
        "temperature": 0.1 
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        if response.status_code == 429: return "Zusammenfassung aktuell nicht verfügbar (Rate Limit)."
        return response.json()['choices'][0]['message']['content'].strip()
    except:
        return "Zusammenfassung aktuell nicht verfügbar."

def scrape_bger():
    print(f"--- Starte Analyse für: {ZIEL_DATUM} ---")
    base_url = "https://www.bger.ch/ext/eurospider/live/de/php/aza/http/index_aza.php?lang=de&mode=index"
    domain = "https://www.bger.ch"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    archiv_daten = []
    archiv_map = {} 
    if os.path.exists('urteile.json'):
        with open('urteile.json', 'r', encoding='utf-8') as f:
            try:
                archiv_daten = json.load(f)
                for d in archiv_daten:
                    archiv_map[d['aktenzeichen']] = d['zusammenfassung']
            except:
                pass

    try:
        res = requests.get(base_url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        tag_link = next((a['href'] for a in soup.find_all('a', href=True) if a.get_text().strip() == ZIEL_DATUM), None)
        
        if not tag_link:
            print("Datum nicht gefunden.")
            return

        day_url = tag_link if tag_link.startswith("http") else domain + tag_link
        day_soup = BeautifulSoup(requests.get(day_url, headers=headers).text, 'html.parser')
        tages_ergebnisse = []
        
        for row in day_soup.find_all('tr'):
            row_text = row.get_text().lower()
            if any(key in row_text for key in KEYWORDS):
                link = row.find('a', href=True)
                if not link: continue
                az = link.get_text().strip()
                if not (az.startswith("9C_") or az.startswith("8C_")): continue
                
                full_link = link['href'] if link['href'].startswith("http") else domain + link['href']
                if az in archiv_map and "nicht verfügbar" not in archiv_map[az]:
                    print(f"Überspringe {az}...")
                    zusammenfassung = archiv_map[az]
                else:
                    print(f"Analysiere: {az}...")
                    case_text = BeautifulSoup(requests.get(full_link, headers=headers).text, 'html.parser').get_text()
                    zusammenfassung = summarize_with_ai(case_text)
                    time.sleep(12) 
                
                tages_ergebnisse.append({"aktenzeichen": az, "datum": ZIEL_DATUM, "zusammenfassung": zusammenfassung, "url": full_link})

        if not tages_ergebnisse:
            tages_ergebnisse.append({"aktenzeichen": "Info", "datum": ZIEL_DATUM, "zusammenfassung": "Keine IV-relevanten Urteile.", "url": domain})

        archiv_daten = [d for d in archiv_daten if d['datum'] != ZIEL_DATUM]
        archiv_daten.extend(tages_ergebnisse)
        archiv_daten.sort(key=lambda x: datetime.strptime(x['datum'], "%d.%m.%Y"), reverse=True)

        with open('urteile.json', 'w', encoding='utf-8') as f:
            json.dump(archiv_daten, f, ensure_ascii=False, indent=4)
        print("Erfolg!")
            
    except Exception as e:
        print(f"Fehler: {e}")

if __name__ == "__main__":
    scrape_bger()
