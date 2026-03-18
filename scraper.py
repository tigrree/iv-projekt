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
    clean_text = " ".join(urteil_text.split()[:2000])
    
    PROMPT_TEXT = """Du bist ein erfahrener Jurist, genauer gesagt ein erfahrener Richter mit Schwerpunkt Sozialversicherungsrecht. Deine Aufgabe ist es, den nachfolgenden Bundesgerichtsentscheid präzise und fachgerecht zusammenzufassen.

Prüfe den ganzen Text und erfinde nichts. Prüfe ausschliesslich, was im Text steht. Beachte dabei folgende strikte Regeln:
1. Anonymisierung:
1.1. Namen von Personen (z. B. B.________) müssen konsequent auf den Buchstaben und den Punkt reduziert werden (Beispiel: B.).
1.2. Wenn die Gutachterstellen ausgeschrieben werden und in Klammern die Abkürzung angegeben wird (Beispiel: Expertise des Centre médical d'expertises = CEMEDEX), dann nur die Abkürzung angeben.
2. Umgang mit Behörden: Wenn das BSV eine Vernehmlassung oder Stellungnahme verfasste, musst du diese aufgreifen. Wenn das BSV keine abgibt, musst du dies nicht erwähnen.
3. Inhaltliche Eingrenzungen (Was wegzulassen ist):
3.1. Lasse das Rubrum und das Dispositiv komplett weg.
3.2. Lasse allgemeine rechtliche Ausführungen weg (z. B. Rügen gemäss Art. 95 lit. a BGG, Rechtsverletzungen nach Art. 95/96 BGG, Anwendung des Rechts von Amtes wegen gemäss Art. 106 Abs. 1 BGG oder Sachverhaltsanpassungen nach Art. 97 Abs. 1 / Art. 105 Abs. 2 BGG).
3.3. Lasse den Teil aus, der sich zu den Prozesskosten äussert.
4. Schreibstil: Keine "ß" sondern jeweils "ss".
5. Wenn du eine Textstelle in die Zusammenfassung nimmst, musst du die Fundstelle, namentlich die Erwägung (bspw. E. 5.2), angeben.

Inhaltliche Schwerpunkte:
1. Sachverhalt: Äussere dich zum materiellen Sachverhalt (inkl. Anträgen und eventualiter Anträge), zur Prozessgeschichte und zum Verfahren vor Bundesgericht in einem Fliesstext. 
2. Medizinische Aspekte: Schenke Ausführungen zu medizinischen Gutachten oder Stellungnahmen des Regionalen Ärztlichen Dienstes (RAD) besondere Aufmerksamkeit.
3. Rechtliche Übergangsbestimmungen: Wenn sich das Gericht zur Weiterentwicklung der IV (WEIV) äussert, erfasse, welches Recht (vor oder nach dem 1.1.2022) gültig ist. Wenn sich das Gericht gar nicht dazu äussert, musst du nichts dazu sagen.

Kernfragen: Beziehe dich darauf, was strittig ist, welches die materiellen Grundlagen sind und was zu prüfen bzw. zu klären ist. Schenke dabei aber besonderen Fokus auf die Begründung und weniger darauf, was zu prüfen ist.

Entscheid: Erfasse am Ende, was das Bundesgericht letztlich entschieden hat (Gutheissung, Abweisung, Rückweisung etc.).

FORMATIERUNG:
**Sachverhalt & Anträge**
[Text]

**Streitig**
[Text]

**Entscheidung**
[Text inkl. Ergebnis]

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
