import requests
from bs4 import BeautifulSoup
import json
import os
import time
from datetime import datetime

# --- DEINE EINSTELLUNG ---
ZIEL_DATUM = "04.02.2026"  # Hier einfach das Datum ändern
# -------------------------

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
IV_SEARCH_TERM = "invalid"

def summarize_with_ai(urteil_text):
    if not GROQ_API_KEY: return "API Key fehlt."
    
    clean_text = " ".join(urteil_text.split()[:750])
    
    PROMPT_TEXT = """
Fasse das Urteil als Schweizer Jurist exakt so zusammen:
**Sachverhalt & Anträge:** [Text]
**Streitig:** [Kern des Streits & anwendbares Recht (altes Recht vor 2022 / neues Recht)]
**Zu prüfen & Entscheidung:** [Begründung & Ergebnis]
Zwingend in Deutsch.
"""
    
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
    print(f"--- Starte manuelle Analyse für: {ZIEL_DATUM} ---")
    base_url = "https://www.bger.ch/ext/eurospider/live/de/php/aza/http/index_aza.php?lang=de&mode=index"
    domain = "https://www.bger.ch"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    # 1. Archiv laden
    archiv_daten = []
    if os.path.exists('urteile.json'):
        with open('urteile.json', 'r', encoding='utf-8') as f:
            archiv_daten = json.load(f)

    try:
        res = requests.get(base_url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # Den Link für das Zieldatum finden
        tag_link = None
        for a in soup.find_all('a', href=True):
            if a.get_text().strip() == ZIEL_DATUM:
                tag_link = a['href']
                break
        
        if not tag_link:
            print(f"Datum {ZIEL_DATUM} wurde auf der BGer-Seite nicht gefunden.")
            return

        # 2. Den Tag scannen
        day_url = tag_link if tag_link.startswith("http") else domain + tag_link
        day_soup = BeautifulSoup(requests.get(day_url, headers=headers).text, 'html.parser')
        tages_ergebnisse = []
        
        for row in day_soup.find_all('tr'):
            if IV_SEARCH_TERM in row.get_text().lower():
                link_tag = row.find('a', href=True)
                if not link_tag: continue
                az = link_tag.get_text().strip()
                if not (az.startswith("9C_") or az.startswith("8C_")): continue
                
                print(f"Verarbeite: {az}...")
                full_link = link_tag['href'] if link_tag['href'].startswith("http") else domain + link_tag['href']
                case_res = requests.get(full_link, headers=headers)
                zusammenfassung = summarize_with_ai(BeautifulSoup(case_res.text, 'html.parser').get_text())
                
                tages_ergebnisse.append({
                    "aktenzeichen": az, "datum": ZIEL_DATUM, 
                    "zusammenfassung": zusammenfassung, "url": full_link
                })
                time.sleep(10) # Kleine Pause

        if not tages_ergebnisse:
            tages_ergebnisse.append({
                "aktenzeichen": "Info", "datum": ZIEL_DATUM, 
                "zusammenfassung": "Keine IV-relevanten Urteile publiziert.", 
                "url": "https://www.bger.ch"
            })

        # 3. Archiv aktualisieren & Sortieren
        archiv_daten = [d for d in archiv_daten if d['datum'] != ZIEL_DATUM]
        archiv_daten.extend(tages_ergebnisse)
        
        # Sortierung (Neueste oben)
        archiv_daten.sort(key=lambda x: datetime.strptime(x['datum'], "%d.%m.%Y"), reverse=True)

        with open('urteile.json', 'w', encoding='utf-8') as f:
            json.dump(archiv_daten, f, ensure_ascii=False, indent=4)
            
        print(f"Fertig! {ZIEL_DATUM} wurde erfolgreich gespeichert.")
            
    except Exception as e:
        print(f"Fehler: {e}")

if __name__ == "__main__":
    scrape_bger()
