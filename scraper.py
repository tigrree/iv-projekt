import requests
from bs4 import BeautifulSoup
import json
import os
import time
import re
from datetime import datetime

# AUTOMATISIERUNG: Nimmt standardmässig das heutige Datum
ZIEL_DATUM = datetime.now().strftime("%d.%m.%Y")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
KEYWORDS = ["invalid"]

def translate_preview(text):
    if not GROQ_API_KEY or not text: return text
    german_indicators = ["invalidenversicherung", "rente", "iv-stelle", "versicherungsgericht"]
    if any(word in text.lower() for word in german_indicators): return text
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "system", "content": "Du bist ein Übersetzer."}, {"role": "user", "content": f"Übersetze kurz: {text}"}],
        "temperature": 0.1 
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        return response.json()['choices'][0]['message']['content'].strip().replace('"', '')
    except: return text

def summarize_with_ai(urteil_text):
    if not GROQ_API_KEY: return "API Key fehlt."
    clean_text = " ".join(urteil_text.split()[:1500])
    PROMPT_TEXT = """Du bist ein erfahrener Bundesrichter. Erstelle eine hochpräzise Zusammenfassung.
STRIKTE REGELN:
1. Anonymisierung: Namen (z. B. A.________) auf Buchstaben mit Punkt reduzieren. Bodenstriche entfernen.
2. Fokus: Gutachten, RAD, WEIV, Verwertbarkeit.
FORMATIERUNG:
**Sachverhalt & Anträge**
**Streitig**
**Entscheidung**"""
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": PROMPT_TEXT + clean_text}], "temperature": 0.1}
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        antwort = response.json()['choices'][0]['message']['content'].strip()
        antwort = re.sub(r'([A-Z]\.)_+', r'\1', antwort)
        return antwort
    except: return "Zusammenfassung aktuell nicht verfügbar."

def scrape_bger():
    print(f"--- Scan für: {ZIEL_DATUM} ---")
    domain = "https://www.bger.ch"
    headers = {'User-Agent': 'Mozilla/5.0'}
    if not os.path.exists('urteile.json'):
        with open('urteile.json', 'w', encoding='utf-8') as f: json.dump([], f)
    with open('urteile.json', 'r', encoding='utf-8') as f:
        try: archiv_daten = json.load(f)
        except: archiv_daten = []

    try:
        base_res = requests.get(f"{domain}/ext/eurospider/live/de/php/aza/http/index_aza.php?lang=de&mode=index", headers=headers)
        soup = BeautifulSoup(base_res.text, 'html.parser')
        tag_link = next((a['href'] for a in soup.find_all('a', href=True) if a.get_text().strip() == ZIEL_DATUM), None)
        if not tag_link: return print(f"Datum {ZIEL_DATUM} noch nicht gelistet.")

        full_tag_url = tag_link if tag_link.startswith("http") else domain + tag_link
        day_soup = BeautifulSoup(requests.get(full_tag_url, headers=headers).text, 'html.parser')
        tages_ergebnisse = []
        rows = day_soup.find_all('tr')
        
        for i in range(len(rows)):
            row = rows[i]
            link_tag = row.find('a', href=True)
            if not link_tag: continue
            raw_az = link_tag.get_text().strip()
            if not (raw_az.startswith("9C_") or raw_az.startswith("8C_")): continue
            
            is_publikation = "*" in raw_az
            clean_az = raw_az.replace("*", "").strip()
            vorschau_text = rows[i+1].get_text().strip() if i + 1 < len(rows) else ""

            if any(key in (row.get_text() + vorschau_text).lower() for key in KEYWORDS):
                case_url = link_tag['href'] if link_tag['href'].startswith("http") else domain + link_tag['href']
                
                # URTEIL LADEN FÜR ROLLEN-CHECK
                case_res = requests.get(case_url, headers=headers)
                case_html = BeautifulSoup(case_res.text, 'html.parser').get_text()
                
                # Check Rolle IV-Stelle Zürich
                iv_zh_fuehrer = False
                iv_zh_gegner = False
                
                beteiligte_part = case_html.split("Sachverhalt:")[0] # Suche nur am Anfang
                if "IV-Stelle des Kantons Zürich" in beteiligte_part:
                    # Suche nach Kontext Beschwerdeführer/Gegner
                    if re.search(r"IV-Stelle des Kantons Zürich.*Beschwerdeführerin", beteiligte_part, re.I):
                        iv_zh_fuehrer = True
                    elif re.search(r"IV-Stelle des Kantons Zürich.*Beschwerdegegnerin", beteiligte_part, re.I):
                        iv_zh_gegner = True

                existing = next((d for d in archiv_daten if d['aktenzeichen'] == clean_az), None)
                if existing and "nicht verfügbar" not in existing['zusammenfassung']:
                    zusammenfassung = existing['zusammenfassung']
                else:
                    zusammenfassung = summarize_with_ai(case_html)
                    time.sleep(2) 

                tages_ergebnisse.append({
                    "aktenzeichen": clean_az, 
                    "datum": ZIEL_DATUM,
                    "publikation": is_publikation,
                    "iv_zh_fuehrer": iv_zh_fuehrer,
                    "iv_zh_gegner": iv_zh_gegner,
                    "vorschau": translate_preview(vorschau_text), 
                    "zusammenfassung": zusammenfassung, 
                    "url": case_url
                })

        if not tages_ergebnisse:
            tages_ergebnisse.append({"aktenzeichen": "INFO_SKIP", "datum": ZIEL_DATUM, "vorschau": "Keine IV-Urteile", "zusammenfassung": "", "url": "", "publikation": False})

        archiv_daten = [d for d in archiv_daten if d['datum'] != ZIEL_DATUM]
        archiv_daten.extend(tages_ergebnisse)
        archiv_daten.sort(key=lambda x: datetime.strptime(x['datum'], "%d.%m.%Y"), reverse=True)
        with open('urteile.json', 'w', encoding='utf-8') as f:
            json.dump(archiv_daten, f, ensure_ascii=False, indent=4)
    except Exception as e: print(f"Fehler: {e}")

if __name__ == "__main__":
    scrape_bger()
