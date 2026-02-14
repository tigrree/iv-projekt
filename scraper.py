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
    
    # 1. Wir nehmen nur die nackten Wörter (entfernt alle Sonderzeichen/Umbrüche)
    words = urteil_text.split()
    clean_text = " ".join(words[:400]) # Wir nehmen nur die ersten 400 Wörter
    
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # 2. Wir nutzen Mixtral, das ist robuster bei Fehlern
    data = {
        "model": "mixtral-8x7b-32768", 
        "messages": [
            {"role": "system", "content": "Du bist ein Schweizer Jurist. Fasse das Urteil in 3 kurzen Sätzen zusammen."},
            {"role": "user", "content": f"Urteilstext: {clean_text}"}
        ],
        "temperature": 0.1
    }
    
    try:
        # Wir senden die Anfrage
        response = requests.post(url, headers=headers, json=data, timeout=30)
        
        # Falls Rate Limit (429), kurz warten
        if response.status_code == 429:
            print("Warte wegen Rate Limit...")
            time.sleep(30)
            return summarize_with_ai(urteil_text)

        response.raise_for_status()
        return response.json()['choices'][0]['message']['content'].strip()
    except Exception as e:
        print(f"Fehler bei KI: {e}")
        return "Zusammenfassung aktuell nicht verfügbar."

def scrape_bger():
    base_url = "https://www.bger.ch/ext/eurospider/live/de/php/aza/http/index_aza.php?lang=de&mode=index"
    domain = "https://www.bger.ch"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    # Archiv laden (um nur Fehlende zu bearbeiten)
    archiv = {}
    if os.path.exists('urteile.json'):
        try:
            with open('urteile.json', 'r', encoding='utf-8') as f:
                alte_daten = json.load(f)
                # Nur Urteile behalten, die eine ECHTE Zusammenfassung haben
                archiv = {d['aktenzeichen']: d['zusammenfassung'] for d in alte_daten 
                          if len(d['zusammenfassung']) > 50 and "verfügbar" not in d['zusammenfassung']}
        except: pass

    neue_liste = []
    try:
        res = requests.get(base_url, headers=headers, timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        date_links = [(a.get_text().strip(), a['href']) for a in soup.find_all('a', href=True) if a.get_text().strip().count('.') == 2]

        for datum, link in date_links:
            day_url = link if link.startswith("http") else domain + link
            day_soup = BeautifulSoup(requests.get(day_url, headers=headers).text, 'html.parser')
            
            for case_link in day_soup.find_all('a', href=True):
                az = case_link.get_text().strip()
                if az.startswith("9C_") or az.startswith("8C_"):
                    if az in archiv:
                        zusammenfassung = archiv[az]
                    else:
                        print(f"Versuche Analyse für: {az}")
                        full_link = case_link['href'] if case_link['href'].startswith("http") else domain + case_link['href']
                        case_page = requests.get(full_link, headers=headers)
                        case_text = BeautifulSoup(case_page.text, 'html.parser').get_text()
                        zusammenfassung = summarize_with_ai(case_text)
                        time.sleep(15) # 15 Sekunden Sicherheitsabstand

                    neue_liste.append({
                        "aktenzeichen": az,
                        "datum": datum,
                        "zusammenfassung": zusammenfassung,
                        "url": case_link['href'] if case_link['href'].startswith("http") else domain + case_link['href']
                    })

        # Info-Meldung für heute
        heute_str = datetime.now().strftime("%d.%m.%Y")
        if not any(d['datum'] == heute_str for d in neue_liste) and datetime.now().weekday() < 5:
            neue_liste.insert(0, {"aktenzeichen": "Info", "datum": heute_str, "zusammenfassung": "Heute wurden keine neuen IV-relevanten Urteile publiziert.", "url": None})

    except Exception as e:
        print(f"Fehler: {e}")

    with open('urteile.json', 'w', encoding='utf-8') as f:
        json.dump(neue_liste, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    scrape_bger()
