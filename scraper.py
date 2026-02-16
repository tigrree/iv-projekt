import requests
from bs4 import BeautifulSoup
import json
import os
import time

# API-Konfiguration (Groq API Key muss als Umgebungsvariable gesetzt sein)
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Der Wortstamm für die Suche (findet auch "Rente d'invalidité" oder "Invalidenversicherung")
IV_SEARCH_TERM = "invalid"

def summarize_with_ai(urteil_text, retries=3):
    """Fasst das Urteil exakt nach juristischen Vorgaben auf Deutsch zusammen."""
    if not GROQ_API_KEY: 
        return "Vorschau im Originalurteil verfügbar (API Key fehlt)."
    
    # Extraktion der ersten 750 Wörter für genügend Kontext
    words = urteil_text.split()
    clean_text = " ".join(words[:750])
    
    # DER ULTIMATIVE PROMPT (Struktur, Intertemporalrecht, Sprache)
    PROMPT_TEXT = """
Du bist ein Schweizer Jurist. Erstelle die Zusammenfassung des folgenden Urteils exakt nach dieser Struktur und ZWINGEND IN DEUTSCHER SPRACHE, auch wenn der Urteilstext in einer anderen Sprache verfasst ist:

### 1. Sachverhalt & Anträge
Fasse hier zusammen: 
- Wer ist die versicherte Person (Jahrgang, Beruf)?
- Welche gesundheitlichen Einschränkungen/Erkrankungen hat die versicherte Person vorgebracht?
- Was hat die IV-Stelle entschieden?
- Wie hat das kantonale Gericht (Vorinstanz) entschieden?
- Was wird mit der Beschwerde in öffentlich-rechtlichen Angelegenheiten vor Bundesgericht konkret gefordert (Anträge)?

### 2. Streitig
Fasse zusammen:
- Was ist im Kern strittig? (Beziehe dich auf die Erwägungen bis zum Beginn der materiellen Prüfung).
- Welches Recht ist anwendbar? (Altes Recht vor 1.1.2022 oder neues Recht ab 1.1.2022 und warum - Intertemporalrecht)?
- Ignoriere Standard-Erwägungen zur Rügepflicht (Art. 95 f. BGG), allgemeine Rechtsfragen und reine Sachverhaltsfragen.

### 3. Zu prüfen & Entscheidung
Fasse zusammen, was das Bundesgericht materiell geprüft hat (z.B. Verwertbarkeit der Restarbeitsfähigkeit, Revisionsgrund) und wie es schlussendlich entschieden hat (Ergebnis mit Begründung).

### FORMATVORLAGE (Halte dich strikt an diese Labels):
**Sachverhalt & Anträge:** [Dein Text]
**Streitig:** [Dein Text inkl. anwendbarem Recht]
**Zu prüfen & Entscheidung:** [Dein Text]

### ANALYSE-MUSTER ALS VORLAGE:
**Sachverhalt & Anträge:** Die 1959 geborene Reinigungsmitarbeiterin meldete sich 2017 an. Die IV-Stelle verneinte 2024 eine Rente, woraufhin das kantonale Gericht die Beschwerde abwies. Vor Bundesgericht wird die Zusprache einer vollen Rente (eventualiter Rückweisung) beantragt.
**Streitig:** Strittig ist die Rentenabweisung. Anwendbar ist das alte Recht (vor 1.1.2022), da der Rentenanspruch bereits 2017 entstand und die Versicherte bei Inkrafttreten der WEIV über 55 Jahre alt war.
**Zu prüfen & Entscheidung:** Zu prüfen war die wirtschaftliche Verwertbarkeit der Restarbeitsfähigkeit. Das Bundesgericht hiess die Beschwerde gut, da eine Anstellung kurz vor dem AHV-Alter nicht mehr realistisch ist.

### URTEILSTEXT ZUR ANALYSE:
"""
    
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": PROMPT_TEXT + clean_text}],
        "temperature": 0.1 
    }
    
    for i in range(retries):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            if response.status_code == 429:
                time.sleep((i + 1) * 45)
                continue
            response.raise_for_status()
            return response.json()['choices'][0]['message']['content'].strip()
        except Exception as e:
            print(f"KI-Fehler: {e}")
            time.sleep(10)
    return "Zusammenfassung aktuell nicht verfügbar."

def scrape_bger():
    """Scrapt das BGer und verarbeitet die letzten 20 Publikationstage."""
    base_url = "https://www.bger.ch/ext/eurospider/live/de/php/aza/http/index_aza.php?lang=de&mode=index"
    domain = "https://www.bger.ch"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    archiv = {}
    if os.path.exists('urteile.json'):
        try:
            with open('urteile.json', 'r', encoding='utf-8') as f:
                alte_daten = json.load(f)
                for d in alte_daten:
                    # Bestehende, gute Zusammenfassungen nicht neu generieren
                    if d['aktenzeichen'] != "Info" and "nicht verfügbar" not in d['zusammenfassung']:
                        archiv[d['aktenzeichen']] = d['zusammenfassung']
        except: pass

    try:
        res = requests.get(base_url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        date_links = [(a.get_text().strip(), a['href']) for a in soup.find_all('a', href=True) if a.get_text().strip().count('.') == 2][:20]
        
        neue_liste = []
        ai_limit = 50 
        ai_counter = 0

        for datum, link in date_links:
            day_url = link if link.startswith("http") else domain + link
            day_soup = BeautifulSoup(requests.get(day_url, headers=headers).text, 'html.parser')
            tages_ergebnisse = []
            
            for row in day_soup.find_all('tr'):
                # Suche in der kompletten Zeile (für Rente d'invalidité etc.)
                if IV_SEARCH_TERM in row.get_text().lower():
                    link_tag = row.find('a', href=True)
                    if not link_tag: continue
                    az = link_tag.get_text().strip()
                    if not (az.startswith("9C_") or az.startswith("8C_")): continue
                    
                    full_link = link_tag['href'] if link_tag['href'].startswith("http") else domain + link_tag['href']
                    
                    if az in archiv:
                        zusammenfassung = archiv[az]
                    elif ai_counter < ai_limit:
                        print(f"Analysiere: {az}...")
                        case_res = requests.get(full_link, headers=headers)
                        zusammenfassung = summarize_with_ai(BeautifulSoup(case_res.text, 'html.parser').get_text())
                        ai_counter += 1
                        time.sleep(25) # API-Schutzpause
                    else:
                        zusammenfassung = "Zusammenfassung aktuell nicht verfügbar (Limit)."

                    tages_ergebnisse.append({"aktenzeichen": az, "datum": datum, "zusammenfassung": zusammenfassung, "url": full_link})
            
            if tages_ergebnisse: neue_liste.extend(tages_ergebnisse)
            else: neue_liste.append({"aktenzeichen": "Info", "datum": datum, "zusammenfassung": "An diesem Tag wurden keine IV-relevanten Urteile publiziert.", "url": "https://www.bger.ch"})

        with open('urteile.json', 'w', encoding='utf-8') as f:
            json.dump(neue_liste, f, ensure_ascii=False, indent=4)
        print(f"Lauf beendet. {ai_counter} neue Analysen erstellt.")
            
    except Exception as e: print(f"Fehler: {e}")

if __name__ == "__main__":
    scrape_bger()
