import requests
from bs4 import BeautifulSoup
import json
import os
import time
from datetime import datetime

# API Key von Groq
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

def summarize_with_ai(urteil_text, retries=2):
    if not GROQ_API_KEY:
        return "Vorschau: Details im Originalurteil verfügbar."
    
    # Text säubern: Zeilenumbrüche und doppelte Leerzeichen entfernen
    clean_text = " ".join(urteil_text.split())
    # Strengere Kürzung auf 3000 Zeichen, um 'Bad Request' zu vermeiden
    short_text = clean_text[:3000]
    
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    prompt = f"Fasse dieses Schweizer IV-Urteil in 3 kurzen Sätzen zusammen (Sachverhalt, Rechtsfrage, Ergebnis). Text: {short_text}"

    data = {
        "model": "llama3-8b-8192",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1 # Noch sachlicher
    }
    
    for i in range(retries):
        try:
            # Wir nutzen json=data, damit requests das Encoding korrekt übernimmt
            response = requests.post(url, headers=headers, json=data, timeout=30)
            
            if response.status_code == 429:
                time.sleep(20)
                continue
                
            response.raise_for_status()
            return response.json()['choices'][0]['message']['content'].strip()
        except Exception as e:
            print(f"Fehler bei KI-Anfrage: {e}")
            time.sleep(5)
    
    return "Zusammenfassung aktuell nicht verfügbar."

def scrape_bger():
    base_url = "https://www.bger.ch/ext/eurospider/live/de/php/aza/http/index_aza.php?lang=de&mode=index"
    domain = "https://www.bger.ch"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    heute_str = datetime.now().strftime("%d.%m.%Y")
    
    # Archiv laden, um Doppelte Arbeit zu vermeiden
    archiv = {}
    if os.path.exists('urteile.json'):
        try:
            with open('urteile.json', 'r', encoding='utf-8') as f:
                alte_daten = json.load(f)
                archiv = {d['aktenzeichen']: d['zusammenfassung'] for d in alte_daten 
                          if d['aktenzeichen'] != "Info" and "nicht verfügbar" not in d['zusammenfassung']}
        except: pass

    neue_liste = []
    
    try:
        res = requests.get(base_url, headers=headers, timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        date_links = [(a.get_text().strip(), a['href']) for a in soup.find_all('a', href=True) if a.get_text().strip().count('.') == 2]

        # Wir begrenzen es auf die letzten 14 Tage (wie vom BGer gelistet)
        for datum, link in date_links:
            day_url = link if link.startswith("http") else domain + link
            day_soup = BeautifulSoup(requests.get(day_url, headers=headers).text, 'html.parser')
            
            for case_link in day_soup.find_all('a', href=True):
                az = case_link.get_text().strip()
                if az.startswith("9C_") or az.startswith("8C_"):
                    if az in archiv:
                        zusammenfassung = archiv[az]
                    else:
                        print(f"Analysiere: {az}")
                        full_link = case_link['href'] if case_link['href'].startswith("http") else domain + case_link['href']
                        case_page = requests.get(full_link, headers=headers)
                        case_text = BeautifulSoup(case_page.text, 'html.parser').get_text()
                        zusammenfassung = summarize_with_ai(case_text)
                        time.sleep(5) # Kurze Pause

                    neue_liste.append({
                        "aktenzeichen": az,
                        "datum": datum,
                        "zusammenfassung": zusammenfassung,
                        "url": case_link['href'] if case_link['href'].startswith("http") else domain + case_link['href']
                    })

        if not any(d['datum'] == heute_str for d in neue_liste) and datetime.now().weekday() < 5:
            neue_liste.insert(0, {"aktenzeichen": "Info", "datum": heute_str, "zusammenfassung": "Heute wurden keine neuen IV-relevanten Urteile publiziert.", "url": None})

    except Exception as e:
        print(f"Fehler: {e}")

    with open('urteile.json', 'w', encoding='utf-8') as f:
        json.dump(neue_liste, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    scrape_bger()
