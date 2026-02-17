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

# Kernbegriffe für maximale Trefferrate
KEYWORDS = ["invalid", "iv-stelle", "office ai", "ufficio ai", "ai"]

def summarize_with_ai(urteil_text):
    if not GROQ_API_KEY: return "API Key fehlt."
    clean_text = " ".join(urteil_text.split()[:750])
    PROMPT_TEXT = "Fasse das Urteil als Schweizer Jurist zusammen: **Sachverhalt & Anträge**, **Streitig**, **Zu prüfen & Entscheidung**. Zwingend Deutsch."
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": PROMPT_TEXT + clean_text}], "temperature": 0.1}
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        return response.json()['choices'][0]['message']['content'].strip()
    except: return "Zusammenfassung aktuell nicht verfügbar."

def scrape_bger():
    print(f"--- Starte Deep-Scan für: {ZIEL_DATUM} ---")
    domain = "https://www.bger.ch"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    archiv_daten = []
    archiv_map = {} 
    if os.path.exists('urteile.json'):
        with open('urteile.json', 'r', encoding='utf-8') as f:
            try:
                archiv_daten = json.load(f)
                for d in archiv_daten: archiv_map[d['aktenzeichen']] = d['zusammenfassung']
            except: pass

    try:
        base_res = requests.get(f"{domain}/ext/eurospider/live/de/php/aza/http/index_aza.php?lang=de&mode=index", headers=headers)
        soup = BeautifulSoup(base_res.text, 'html.parser')
        tag_link = next((a['href'] for a in soup.find_all('a', href=True) if a.get_text().strip() == ZIEL_DATUM), None)
        
        if not tag_link: return print("Datum nicht gefunden.")

        day_url = tag_link if tag_link.startswith("http") else domain + tag_link
        day_soup = BeautifulSoup(requests.get(day_url, headers=headers).text, 'html.parser')
        tages_ergebnisse = []
        
        # Alle Tabellenzeilen finden
        rows = day_soup.find_all('tr')
        
        # FIX: Korrekte Syntax für die Schleife (ohne das hängende Komma)
        for i in range(len(rows)):
            row = rows[i]
            link_tag = row.find('a', href=True)
            if not link_tag: continue
            
            az = link_tag.get_text().strip()
            if not (az.startswith("9C_") or az.startswith("8C_")): continue
            
            # Look-Ahead Logik: Aktuelle Zeile + nächste Zeile kombinieren
            current_row_text = row.get_text(separator=" ")
            next_row_text = ""
            if i + 1 < len(rows):
                next_row_text = rows[i+1].get_text(separator=" ")
            
            combined_context = (current_row_text + " " + next_row_text).lower()
            
            if any(key in combined_context for key in KEYWORDS):
                full_link = link_tag['href'] if link_tag['href'].startswith("http") else domain + link_tag['href']
                
                if az in archiv_map and "nicht verfügbar" not in archiv_map[az]:
                    print(f"Überspringe: {az}")
                    zusammenfassung = archiv_map[az]
                else:
                    print(f"!!! GEFUNDEN: {az} !!!")
                    case_text = BeautifulSoup(requests.get(full_link, headers=headers).text, 'html.parser').get_text()
                    zusammenfassung = summarize_with_ai(case_text)
                    time.sleep(10)
                
                if not any(e['aktenzeichen'] == az for e in tages_ergebnisse):
                    tages_ergebnisse.append({"aktenzeichen": az, "datum": ZIEL_DATUM, "zusammenfassung": zusammenfassung, "url": full_link})

        if not tages_ergebnisse:
            tages_ergebnisse.append({"aktenzeichen": "Info", "datum": ZIEL_DATUM, "zusammenfassung": "Keine IV-Urteile.", "url": domain})

        archiv_daten = [d for d in archiv_daten if d['datum'] != ZIEL_DATUM]
        archiv_daten.extend(tages_ergebnisse)
        archiv_daten.sort(key=lambda x: datetime.strptime(x['datum'], "%d.%m.%Y"), reverse=True)

        with open('urteile.json', 'w', encoding='utf-8') as f:
            json.dump(archiv_daten, f, ensure_ascii=False, indent=4)
        print("Erfolg!")
            
    except Exception as e: print(f"Fehler: {e}")

if __name__ == "__main__":
    scrape_bger()
