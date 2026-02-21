import requests
from bs4 import BeautifulSoup
import json
import os
import time
import re  # Erlaubt das Suchen und Ersetzen von Mustern
from datetime import datetime

# TEST-MODUS: Datum manuell auf den 20.02.2026 gesetzt
ZIEL_DATUM = "20.02.2026"

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
KEYWORDS = ["invalid"]

def translate_preview(text):
    """Übersetzt nur, wenn es absolut notwendig ist (z.B. Französisch/Italienisch)."""
    if not GROQ_API_KEY or not text: return text
    
    # Falls Deutsch bereits erkannt wird, nichts tun
    german_indicators = ["invalidenversicherung", "rente", "iv-stelle", "versicherungsgericht"]
    if any(word in text.lower() for word in german_indicators):
        return text

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": "Du bist ein Übersetzer für Schweizer Rechtsterminologie. Antworte NUR mit der Übersetzung des Begriffs. Keine Erklärungen, keine Einleitung."},
            {"role": "user", "content": f"Übersetze diesen juristischen Begriff kurz ins Deutsche: {text}"}
        ],
        "temperature": 0.1 
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        return response.json()['choices'][0]['message']['content'].strip().replace('"', '')
    except: return text

def summarize_with_ai(urteil_text):
    if not GROQ_API_KEY: return "API Key fehlt."
    clean_text = " ".join(urteil_text.split()[:1500])
    
    PROMPT_TEXT = """
Du bist ein erfahrener Bundesrichter mit Schwerpunkt Sozialversicherungsrecht. Erstelle eine hochpräzise juristische Zusammenfassung.

STRIKTE REGELN:
1. Anonymisierung: Namen (z. B. A.________ oder A. A.________) konsequent auf den Buchstaben mit Punkt reduzieren (Beispiel: 'A.' oder 'A. A.'). Bodenstriche nach dem Punkt müssen ZWINGEND entfernt werden.
2. Prozessgeschichte: Erfasse genau die Vorinstanz und den Weg zum Bundesgericht.
3. Medizin: Fokus auf Gutachten (ABI, SMAB etc.) vs. Hausärzte. RAD explizit erwähnen.
4. WEIV: Unterteile Prüfung in Zeiträume vor/nach 1.1.2024, falls relevant.
5. Verwertbarkeit: Gehe auf die Verwertbarkeit der Restarbeitsfähigkeit ein.

FORMATIERUNG:
**Sachverhalt & Anträge**
[Text]

**Streitig**
[Text]

**Zu prüfen & Entscheidung**
[Text inkl. Ergebnis]

Antworte NUR in Deutsch. Keine Einleitung.
Hier ist das Urteil:
"""
    
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": "Du bist ein Schweizer Bundesrichter. Deine Zusammenfassungen sind präzise und frei von Bodenstrichen bei Namen."},
            {"role": "user", "content": PROMPT_TEXT + clean_text}
        ],
        "temperature": 0.1
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        antwort = response.json()['choices'][0]['message']['content'].strip()
        
        # TECHNISCHE REINIGUNG (Regex): 
        antwort = re.sub(r'([A-Z]\.)_+', r'\1', antwort)
        antwort = re.sub(r'([A-Z]\s[A-Z]\.)_+', r'\1', antwort)
        
        return antwort
    except:
        return "Zusammenfassung aktuell nicht verfügbar."

def scrape_bger():
    print(f"--- Starte TEST-Scan für: {ZIEL_DATUM} ---")
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
            az = link_tag.get_text().strip()
            if not (az.startswith("9C_") or az.startswith("8C_")): continue
            
            vorschau_text = ""
            if i + 1 < len(rows):
                potential_detail = rows[i+1].get_text().strip()
                if not (potential_detail.startswith("8C_") or potential_detail.startswith("9C_")):
                    vorschau_text = potential_detail
            
            full_context = row.get_text() + " " + (rows[i+1].get_text() if i+1 < len(rows) else "")
            
            if any(key in full_context.lower() for key in KEYWORDS):
                print(f"Treffer gefunden: {az}")
                case_url = link_tag['href'] if link_tag['href'].startswith("http") else domain + link_tag['href']
                
                # Wir löschen bestehende Einträge für diesen Tag im Test, damit die KI neu generiert
                archiv_daten = [d for d in archiv_daten if d['aktenzeichen'] != az]
                
                print(f"KI-Analyse für {az}...")
                case_res = requests.get(case_url, headers=headers)
                zusammenfassung = summarize_with_ai(BeautifulSoup(case_res.text, 'html.parser').get_text())
                time.sleep(2) 

                tages_ergebnisse.append({
                    "aktenzeichen": az, "datum": ZIEL_DATUM,
                    "vorschau": translate_preview(vorschau_text), 
                    "zusammenfassung": zusammenfassung, "url": case_url
                })

        if not tages_ergebnisse:
            tages_ergebnisse.append({
                "aktenzeichen": "INFO_SKIP", "datum": ZIEL_DATUM,
                "vorschau": "Keine IV-Urteile publiziert", "zusammenfassung": "", "url": ""
            })

        archiv_daten = [d for d in archiv_daten if d['datum'] != ZIEL_DATUM]
        archiv_daten.extend(tages_ergebnisse)
        archiv_daten.sort(key=lambda x: datetime.strptime(x['datum'], "%d.%m.%Y"), reverse=True)
        
        # 14-Tage Limit
        alle_tage = sorted(list(set(d['datum'] for d in archiv_daten)), key=lambda x: datetime.strptime(x, "%d.%m.%Y"))
        while len(alle_tage) > 14:
            archiv_daten = [d for d in archiv_daten if d['datum'] != alle_tage[0]]
            alle_tage.pop(0)

        with open('urteile.json', 'w', encoding='utf-8') as f:
            json.dump(archiv_daten, f, ensure_ascii=False, indent=4)
        print(f"Test-Scan für {ZIEL_DATUM} abgeschlossen.")
            
    except Exception as e: print(f"Fehler: {e}")

if __name__ == "__main__":
    scrape_bger()
