import requests
from bs4 import BeautifulSoup
import json
import os
import time
from datetime import datetime

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

def summarize_with_ai(urteil_text):
    if not GROQ_API_KEY:
        return "Vorschau im Originalurteil verfügbar."
    
    # Text-Vorbereitung: Nur die ersten 400 Wörter für die KI
    words = urteil_text.split()
    clean_text = " ".join(words[:400])
    
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": "mixtral-8x7b-32768", 
        "messages": [
            {"role": "system", "content": "Du bist ein Schweizer Jurist. Fasse das Urteil in 3 kurzen Sätzen zusammen (Sachverhalt, Rechtsfrage, Ergebnis)."},
            {"role": "user", "content": f"Urteilstext: {clean_text}"}
        ],
        "temperature": 0.1
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        if response.status_code == 429:
            print("Rate Limit erreicht. Warte 30 Sek...")
            time.sleep(30)
            return summarize_with_ai(urteil_text)
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content'].strip()
    except Exception as e:
        print(f"KI Fehler: {e}")
        return "Zusammenfassung aktuell nicht verfügbar."

def scrape_bger():
    base_url = "https://www.bger.ch/ext/eurospider/live/de/php/aza/http/index_aza.php?lang=de&mode=index"
    domain = "https://www.bger.ch"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    # Archiv laden
    archiv = {}
    if os.path.exists('urteile.json'):
        try:
            with open('urteile.json', 'r', encoding='utf-8') as f:
                alte_daten = json.load(f)
                # Wir behalten nur Urteile, die bereits eine richtige Zusammenfassung haben
                archiv = {d['aktenzeichen']: d['zusammenfassung'] for d in alte_daten 
                          if len(d['zusammenfassung']) > 50 and "verfügbar" not in d['zusammenfassung']}
        except: pass

    try:
        res = requests.get(base_url, headers=headers, timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        date_links = [(a.get_text().strip(), a['href']) for a in soup.find_all('a', href=True) if a.get_text().strip().count('.') == 2]

        # --- DIE NEUE LOGIK: Chronologisch von alt nach neu ---
        date_links.reverse() # Wir fangen beim ältesten Datum (27.01.) an
        
        neue_liste = []
        limit_pro_lauf = 8 # Wir machen max. 8 NEUE Analysen pro Durchgang, um die API zu schonen
        counter = 0

        for datum, link in date_links:
            day_url = link if link.startswith("http") else domain + link
            day_soup = BeautifulSoup(requests.get(day_url, headers=headers).text, 'html.parser')
            
            for case_link in day_soup.find_all('a', href=True):
                az = case_link.get_text().strip()
                if az.startswith("9C_") or az.startswith("8C_"):
                    full_link = case_link['href'] if case_link['href'].startswith("http") else domain + case_link['href']
                    
                    if az in archiv:
                        zusammenfassung = archiv[az]
                    elif counter < limit_pro_lauf:
                        print(f"Analysiere NEUES Urteil ({counter+1}/{limit_pro_lauf}): {az}")
                        case_page = requests.get(full_link, headers=headers)
                        case_text = BeautifulSoup(case_page.text, 'html.parser').get_text()
                        zusammenfassung = summarize_with_ai(case_text)
                        counter += 1
                        time.sleep(20) # Sicherheitsabstand
                    else:
                        zusammenfassung = "Wird im nächsten Durchlauf analysiert..."

                    neue_liste.append({
                        "aktenzeichen": az,
                        "datum": datum,
                        "zusammenfassung": zusammenfassung,
                        "url": full_link
                    })

        # Liste für die Anzeige wieder umdrehen (Neueste oben)
        neue_liste.reverse()

        # Info-Meldung für heute (Wochentag-Check)
        heute_str = datetime.now().strftime("%d.%m.%Y")
        if not any(d['datum'] == heute_str for d in neue_liste) and datetime.now().weekday() < 5:
            neue_liste.insert(0, {"aktenzeichen": "Info", "datum": heute_str, "zusammenfassung": "Heute wurden keine neuen IV-Urteile publiziert.", "url": None})

        # Speichern
        with open('urteile.json', 'w', encoding='utf-8') as f:
            json.dump(neue_liste, f, ensure_ascii=False, indent=4)
            
    except Exception as e:
        print(f"Grober Fehler: {e}")

if __name__ == "__main__":
    scrape_bger()
