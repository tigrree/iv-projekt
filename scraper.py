import requests
from bs4 import BeautifulSoup
import json
import os
import time

# API-Konfiguration
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
IV_SEARCH_TERM = "invalid"

def summarize_with_ai(urteil_text, retries=3):
    """Fasst das Urteil auf Deutsch zusammen und fängt Rate-Limits ab."""
    if not GROQ_API_KEY: 
        return "Vorschau im Originalurteil verfügbar (API Key fehlt)."
    
    words = urteil_text.split()
    clean_text = " ".join(words[:750])
    
    PROMPT_TEXT = """
Du bist ein Schweizer Jurist. Erstelle die Zusammenfassung des folgenden Urteils exakt nach dieser Struktur und ZWINGEND IN DEUTSCHER SPRACHE:

### 1. Sachverhalt & Anträge
- Wer (Jahrgang, Beruf)?
- Welche Einschränkungen/Erkrankungen?
- Entscheid IV-Stelle?
- Entscheid Vorinstanz?
- Anträge vor Bundesgericht?

### 2. Streitig
- Kern des Streits?
- Anwendbares Recht (Intertemporalrecht: Altes Recht vor 1.1.2022 / Neues Recht ab 1.1.2022) und warum?

### 3. Zu prüfen & Entscheidung
- Materielle Prüfung & Ergebnis mit Begründung.

FORMATVORLAGE:
**Sachverhalt & Anträge:** [Text]
**Streitig:** [Text]
**Zu prüfen & Entscheidung:** [Text]
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
            if response.status_code == 429: # Rate Limit
                time.sleep((i + 1) * 45)
                continue
            response.raise_for_status()
            return response.json()['choices'][0]['message']['content'].strip()
        except Exception as e:
            print(f"KI-Fehler: {e}")
            time.sleep(10)
            
    return "Zusammenfassung aktuell nicht verfügbar."

def scrape_bger():
    """Verarbeitet pro Durchlauf genau einen noch nicht (korrekt) bearbeiteten Tag."""
    base_url = "https://www.bger.ch/ext/eurospider/live/de/php/aza/http/index_aza.php?lang=de&mode=index"
    domain = "https://www.bger.ch"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    # 1. Archiv laden und Status prüfen
    archiv_daten = []
    bearbeitete_tage = set()
    archiv_map = {} # Schneller Zugriff auf Aktenzeichen

    if os.path.exists('urteile.json'):
        try:
            with open('urteile.json', 'r', encoding='utf-8') as f:
                archiv_daten = json.load(f)
                for d in archiv_daten:
                    # Wir mappen Aktenzeichen zu ihrem Inhalt
                    archiv_map[d['aktenzeichen']] = d['zusammenfassung']
                    
                    # Ein Tag gilt nur als bearbeitet, wenn er kein "nicht verfügbar" enthält
                    if "nicht verfügbar" not in d['zusammenfassung']:
                        bearbeitete_tage.add(d['datum'])
        except: pass

    try:
        res = requests.get(base_url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        # Liste aller Tage (neueste oben)
        alle_tage = [(a.get_text().strip(), a['href']) for a in soup.find_all('a', href=True) if a.get_text().strip().count('.') == 2]
        
        # 2. Den ältesten unfertigen Tag finden (Liste umkehren)
        ziel_tag = None
        for datum, link in reversed(alle_tage):
            # Wenn der Tag noch nie gescannt wurde ODER Lücken ("nicht verfügbar") enthält
            if datum not in bearbeitete_tage:
                ziel_tag = (datum, link)
                break
        
        if not ziel_tag:
            print("Alle Tage sind bereits vollständig verarbeitet!")
            return

        datum, link = ziel_tag
        print(f"--- Starte gezielte Analyse für Tag: {datum} ---")
        
        day_url = link if link.startswith("http") else domain + link
        day_soup = BeautifulSoup(requests.get(day_url, headers=headers).text, 'html.parser')
        tages_ergebnisse = []
        
        for row in day_soup.find_all('tr'):
            if IV_SEARCH_TERM in row.get_text().lower():
                link_tag = row.find('a', href=True)
                if not link_tag: continue
                az = link_tag.get_text().strip()
                if not (az.startswith("9C_") or az.startswith("8C_")): continue
                
                full_link = link_tag['href'] if link_tag['href'].startswith("http") else domain + link_tag['href']
                
                # Prüfen, ob wir dieses spezifische Urteil schon sauber haben
                if az in archiv_map and "nicht verfügbar" not in archiv_map[az]:
                    zusammenfassung = archiv_map[az]
                    print(f"Überspringe (bereits fertig): {az}")
                else:
                    print(f"Analysiere neu: {az}...")
                    case_res = requests.get(full_link, headers=headers)
                    zusammenfassung = summarize_with_ai(BeautifulSoup(case_res.text, 'html.parser').get_text())
                    time.sleep(20) # API-Schutz

                tages_ergebnisse.append({
                    "aktenzeichen": az, 
                    "datum": datum, 
                    "zusammenfassung": zusammenfassung, 
                    "url": full_link
                })
        
        if not tages_ergebnisse:
            tages_ergebnisse.append({
                "aktenzeichen": "Info", "datum": datum, 
                "zusammenfassung": "Keine IV-relevanten Urteile publiziert.", 
                "url": "https://www.bger.ch"
            })

        # 3. Archiv aktualisieren: Alten Stand des Tages löschen, neuen hinzufügen
        archiv_daten = [d for d in archiv_daten if d['datum'] != datum]
        archiv_daten.extend(tages_ergebnisse)

        # Finales Speichern
        with open('urteile.json', 'w', encoding='utf-8') as f:
            json.dump(archiv_daten, f, ensure_ascii=False, indent=4)
            
        print(f"Erfolg! Tag {datum} wurde aktualisiert.")
            
    except Exception as e:
        print(f"Kritischer Fehler: {e}")

if __name__ == "__main__":
    scrape_bger()
