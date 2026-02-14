import requests
from bs4 import BeautifulSoup
import json
import os
import time
from datetime import datetime

# API Key von Groq
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

def summarize_with_ai(urteil_text, retries=3):
    if not GROQ_API_KEY:
        return "Vorschau: Details im Originalurteil verfügbar."
    
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    prompt = f"""Du bist ein spezialisierter Jurist für Schweizer Sozialversicherungsrecht. 
    Fasse das folgende Urteil zur Invalidenversicherung (IV) in maximal 3 prägnanten Sätzen zusammen.
    Konzentriere dich auf: 1. Sachverhalt, 2. Rechtsfrage, 3. Ergebnis.
    
    Text: {urteil_text[:3500]}"""

    data = {
        "model": "llama3-8b-8192",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2
    }
    
    for i in range(retries):
        try:
            response = requests.post(url, headers=headers, json=data, timeout=20)
            if response.status_code == 429: # Rate Limit getroffen
                print(f"Rate Limit erreicht. Warte 20 Sekunden... (Versuch {i+1}/{retries})")
                time.sleep(20)
                continue
            
            response.raise_for_status()
            return response.json()['choices'][0]['message']['content'].strip()
        except Exception as e:
            print(f"Fehler bei KI-Anfrage: {e}")
            time.sleep(5)
    
    return "Zusammenfassung aktuell nicht verfügbar. Bitte Originalurteil prüfen."

def scrape_bger():
    base_url = "https://www.bger.ch/ext/eurospider/live/de/php/aza/http/index_aza.php?lang=de&mode=index"
    domain = "https://www.bger.ch"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    heute_str = datetime.now().strftime("%d.%m.%Y")
    
    # Vorhandene Daten laden
    archiv = {}
    if os.path.exists('urteile.json'):
        try:
            with open('urteile.json', 'r', encoding='utf-8') as f:
                alte_daten = json.load(f)
                archiv = {d['aktenzeichen']: d['zusammenfassung'] for d in alte_daten 
                          if d['aktenzeichen'] != "Info" and "nicht generiert" not in d['zusammenfassung']}
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
                    # Wenn wir eine gute Zusammenfassung haben, behalten wir sie
                    if az in archiv:
                        zusammenfassung = archiv[az]
                    else:
                        print(f"Analysiere neues Urteil: {az}")
                        full_link = case_link['href'] if case_link['href'].startswith("http") else domain + case_link['href']
                        case_text = BeautifulSoup(requests.get(full_link, headers=headers).text, 'html.parser').get_text()
                        zusammenfassung = summarize_with_ai(case_text)
                        time.sleep(10) # 10 Sekunden Pause zwischen JEDEM Urteil (wichtig für Free Tier!)

                    neue_liste.append({
                        "aktenzeichen": az,
                        "datum": datum,
                        "zusammenfassung": zusammenfassung,
                        "url": case_link['href'] if case_link['href'].startswith("http") else domain + case_link['href']
                    })

        # Info-Meldung für heute
        if not any(d['datum'] == heute_str for d in neue_liste) and datetime.now().weekday() < 5:
            neue_liste.insert(0, {"aktenzeichen": "Info", "datum": heute_str, "zusammenfassung": "Heute wurden keine neuen IV-relevanten Urteile publiziert.", "url": None})

    except Exception as e:
        print(f"Fehler: {e}")

    with open('urteile.json', 'w', encoding='utf-8') as f:
        json.dump(neue_liste, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    scrape_bger()
