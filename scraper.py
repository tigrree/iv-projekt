import requests
from bs4 import BeautifulSoup
import json
import os
import time
from datetime import datetime

# --- EINSTELLUNG ---
# Für morgen dann wieder datetime.now().strftime("%d.%m.%Y")
ZIEL_DATUM = "17.02.2026" 
# -------------------

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
KEYWORDS = ["invalid"]

def summarize_with_ai(urteil_text):
    if not GROQ_API_KEY: return "API Key fehlt."
    clean_text = " ".join(urteil_text.split()[:750])
    PROMPT_TEXT = """
Fasse das Urteil als Schweizer Jurist exakt in diesem Format zusammen:
**Sachverhalt & Anträge**\n[Hier Text einfügen]

**Streitig:**\n[Hier Text einfügen]

**Zu prüfen & Entscheidung:**\n[Hier Text einfügen]

Zwingend in Deutsch antworten. Keine Einleitung, nur dieser Block.
"""
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": PROMPT_TEXT + clean_text}], "temperature": 0.1}
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        return response.json()['choices'][0]['message']['content'].strip()
    except: return "Zusammenfassung aktuell nicht verfügbar."

def scrape_bger():
    print(f"--- Starte Präzisions-Scan für: {ZIEL_DATUM} ---")
    domain = "https://www.bger.ch"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    if not os.path.exists('urteile.json'):
        with open('urteile.json', 'w', encoding='utf-8') as f: json.dump([], f)
    with open('urteile.json', 'r', encoding='utf-8') as f:
        archiv_daten = json.load(f)

    try:
        base_url = f"{domain}/ext/eurospider/live/de/php/aza/http/index_aza.php?lang=de&mode=index"
        res = requests.get(base_url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        tag_link = next((a['href'] for a in soup.find_all('a', href=True) if a.get_text().strip() == ZIEL_DATUM), None)
        
        if not tag_link: return print("Datum nicht gefunden.")

        day_soup = BeautifulSoup(requests.get(tag_link if tag_link.startswith("http") else domain + tag_link, headers=headers).text, 'html.parser')
        tages_ergebnisse = []
        rows = day_soup.find_all('tr')
        
        for i in range(len(rows)):
            row = rows[i]
            link_tag = row.find('a', href=True)
            if not link_tag: continue
            
            az = link_tag.get_text().strip()
            if not (az.startswith("9C_") or az.startswith("8C_")): continue
            
            # --- LOGIK FÜR KOMBINIERTE VORSCHAU ---
            text_parts = [t.strip() for t in row.find_all(string=True) if t.strip()]
            
            vorschau_text = ""
            try:
                idx = text_parts.index(az)
                # Wir schauen, was nach dem Aktenzeichen kommt
                remaining = text_parts[idx+1:]
                
                if len(remaining) >= 2:
                    # Kombiniere das erste Wort (z.B. Invalidenversicherung) 
                    # mit dem direkt darauffolgenden Teil (z.B. die Klammer)
                    part1 = remaining[0]
                    part2 = remaining[1]
                    
                    # Falls part2 bereits eine Klammer ist, einfach anhängen
                    if part2.startswith("("):
                        vorschau_text = f"{part1} {part2}"
                    else:
                        # Ansonsten mit Klammer formatieren
                        vorschau_text = f"{part1} ({part2})"
                elif len(remaining) == 1:
                    vorschau_text = remaining[0]
            except ValueError:
                vorschau_text = "Sachgebiet unbekannt"
            
            # --------------------------------------

            ctx = (row.get_text() + " " + (rows[i+1].get_text() if i+1 < len(rows) else "")).lower()
            if any(key in ctx for key in KEYWORDS):
                print(f"Treffer: {az} | Vorschau: {vorschau_text}")
                case_url = link_tag['href'] if link_tag['href'].startswith("http") else domain + link_tag['href']
                
                existing = next((d for d in archiv_daten if d['aktenzeichen'] == az), None)
                if existing and "nicht verfügbar" not in existing['zusammenfassung'] and existing['zusammenfassung'] != "":
                    zusammenfassung = existing['zusammenfassung']
                else:
                    print(f"Analysiere {az}...")
                    text = BeautifulSoup(requests.get(case_url, headers=headers).text, 'html.parser').get_text()
                    zusammenfassung = summarize_with_ai(text)
                    time.sleep(12)

                tages_ergebnisse.append({
                    "aktenzeichen": az, 
                    "datum": ZIEL_DATUM,
                    "vorschau": vorschau_text,
                    "zusammenfassung": zusammenfassung, 
                    "url": case_url
                })

        archiv_daten = [d for d in archiv_daten if d['datum'] != ZIEL_DATUM]
        archiv_daten.extend(tages_ergebnisse)
        archiv_daten.sort(key=lambda x: datetime.strptime(x['datum'], "%d.%m.%Y"), reverse=True)
        
        with open('urteile.json', 'w', encoding='utf-8') as f:
            json.dump(archiv_daten, f, ensure_ascii=False, indent=4)
        print("Erfolg!")
            
    except Exception as e: print(f"Fehler: {e}")

if __name__ == "__main__":
    scrape_bger()
