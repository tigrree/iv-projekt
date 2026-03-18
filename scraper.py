import requests
from bs4 import BeautifulSoup
import json
import os
import time
import re
from datetime import datetime

# AUTOMATISIERUNG: Nimmt standardmässig das heutige Datum
ZIEL_DATUM = "12.03.2026"

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
    clean_text = " ".join(urteil_text.split()[:2000])
    
    PROMPT_TEXT = """Du bist ein erfahrener Jurist, genauer gesagt ein erfahrener Richter mit Schwerpunkt Sozialversicherungsrecht. Deine Aufgabe ist es, den nachfolgenden Bundesgerichtsentscheid präzise und fachgerecht zusammenzufassen.

### WICHTIGSTE REGEL FÜR DIE LOGIK:
Prüfe ZUERST am Ende des Textes im Dispositiv oder den letzten Erwägungen, ob die Beschwerde GUTGEHEISSEN, ABGEWIESEN oder die Sache RÜCKGEWIESEN wurde. 
- Wenn das Bundesgericht das kantonale Urteil AUFHEBT oder die Sache RÜCKWEIST, darfst du die rechtliche Begründung der Vorinstanz NICHT als korrekt darstellen.
- Unterscheide strikt zwischen: "Die Vorinstanz stellte fest..." (Vergangenheit/falsch) und "Das Bundesgericht hingegen erkennt..." (Massgebend).

### Strikte Regeln:
1. Anonymisierung:
1.1. Namen von Personen konsequent auf den Buchstaben und den Punkt reduzieren (Beispiel: A.).
1.2. Gutachterstellen: Nur die Abkürzung angeben (z.B. ZMB statt Zentrum für Medizinische Begutachtung).
2. Behörden: Stellungnahmen des BSV nur erwähnen, wenn vorhanden.
3. Inhaltliche Eingrenzungen (Weglassen):
3.1. Rubrum und Dispositiv (als Textblock) weglassen.
3.2. Standard-Floskeln zu Art. 95, 97, 105, 106 BGG weglassen.
3.3. Prozesskosten/Entschädigungen weglassen.
4. Schreibstil: "ss" statt "ß".
5. **Referenzierung: Jede inhaltliche Aussage muss zwingend mit der entsprechenden Erwägung (z.B. E. 5.2) belegt werden.**

### Inhaltliche Schwerpunkte:
1. Sachverhalt: Materieller Sachverhalt, Anträge, Prozessgeschichte (Vorinstanz) und Verfahren vor Bundesgericht als Fliesstext.
2. Medizinische Aspekte: Fokus auf Gutachten und RAD-Stellungnahmen. **Halte fest, ob das Bundesgericht den Beweiswert dieser Unterlagen bestätigt oder kritisiert.**
3. Übergangsrecht: Falls WEIV (altes vs. neues Recht ab 1.1.2022) thematisiert wird, kurz erwähnen, welches Recht anwendbar ist.

### Kernfragen & Begründung:
- Was ist strittig?
- **Fokus auf die Begründung des Bundesgerichts:** Warum kippt oder bestätigt das Bundesgericht das vorinstanzliche Urteil? 
- **Stelle sicher, dass du nicht die Argumente der Vorinstanz als Endergebnis wiedergibst.**

### Entscheid:
Nenne am Ende klar das Ergebnis: Gutheissung, teilweise Gutheissung, Abweisung oder Rückweisung.

FORMATIERUNG:
**Sachverhalt & Anträge**
[Text]

**Streitig**
[Text]

**Entscheidung**
[Detaillierte Begründung des Bundesgerichts unter Angabe der Erwägungen + Endergebnis]

Antworte NUR in Deutsch. Keine Einleitung.
Hier ist das Urteil:
"""
    
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": "Du bist ein erfahrener Schweizer Bundesrichter. Du nutzt ausschliesslich 'ss' statt 'ß' und zitierst Erwägungen präzise."},
            {"role": "user", "content": PROMPT_TEXT + clean_text}
        ],
        "temperature": 0.1
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        antwort = response.json()['choices'][0]['message']['content'].strip()
        antwort = re.sub(r'([A-Z]\.)_+', r'\1', antwort)
        antwort = re.sub(r'([A-Z]\s[A-Z]\.)_+', r'\1', antwort)
        return antwort
    except Exception as e:
        print(f"Fehler bei der KI-Anfrage: {e}")
        return "Zusammenfassung aktuell nicht verfügbar."

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
                print(f"Treffer gefunden: {clean_az}")
                case_url = link_tag['href'] if link_tag['href'].startswith("http") else domain + link_tag['href']
                
                case_res = requests.get(case_url, headers=headers)
                case_html = BeautifulSoup(case_res.text, 'html.parser').get_text()
                
                iv_zh_fuehrer = False
                iv_zh_gegner = False
                
                beteiligte_part = case_html.split("Sachverhalt:")[0]
                search_text = " ".join(beteiligte_part.split())
                
                if "IV-Stelle des Kantons Zürich" in search_text:
                    if "Beschwerdeführerin" in search_text:
                        iv_zh_fuehrer = True
                    elif "Beschwerdegegnerin" in search_text:
                        iv_zh_gegner = True

                existing = next((d for d in archiv_daten if d['aktenzeichen'] == clean_az), None)
                if existing and "nicht verfügbar" not in existing['zusammenfassung']:
                    zusammenfassung = existing['zusammenfassung']
                    existing["iv_zh_fuehrer"] = iv_zh_fuehrer
                    existing["iv_zh_gegner"] = iv_zh_gegner
                    existing["publikation"] = is_publikation
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
            # ANGEPASSTER TEXT IM SPEICHER-PROZESS
            tages_ergebnisse.append({"aktenzeichen": "INFO_SKIP", "datum": ZIEL_DATUM, "vorschau": "Keine neuen IV-relevanten Urteile", "zusammenfassung": "", "url": "", "publikation": False})

        archiv_daten = [d for d in archiv_daten if d['datum'] != ZIEL_DATUM]
        archiv_daten.extend(tages_ergebnisse)
        archiv_daten.sort(key=lambda x: datetime.strptime(x['datum'], "%d.%m.%Y"), reverse=True)
        
        with open('urteile.json', 'w', encoding='utf-8') as f:
            json.dump(archiv_daten, f, ensure_ascii=False, indent=4)
        print(f"Scan für {ZIEL_DATUM} abgeschlossen.")

    except Exception as e: print(f"Fehler: {e}")

if __name__ == "__main__":
    scrape_bger()
