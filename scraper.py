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
    
    # 1. Radikale Text-Vorbereitung: Nur reiner Text, max 400 Wörter
    clean_text = " ".join(urteil_text.split()[:400])
    
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # 2. Absolut minimalistisches JSON-Format
    payload = {
        "model": "mixtral-8x7b-32768",
        "messages": [
            {"role": "user", "content": f"Fasse kurz in 3 Saetzen zusammen: {clean_text}"}
        ],
        "temperature": 0.1
    }
    
    try:
        # json=payload stellt sicher, dass Python das Encoding perfekt übernimmt
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 429:
            time.sleep(30)
            return summarize_with_ai(urteil_text)
            
        if response.status_code != 200:
            print(f"API Fehler {response.status_code}: {response.text}")
            return "Zusammenfassung aktuell nicht verfügbar."
            
        return response.json()['choices'][0]['message']['content'].strip()
    except Exception as e:
        print(f"Systemfehler: {e}")
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
                # Nur ECHTE Zusammenfassungen behalten
                archiv = {d['aktenzeichen']: d['zusammenfassung'] for d in alte_daten 
                          if len(d['zusammenfassung']) > 50 and "verfügbar" not in d['zusammenfassung']}
        except: pass

    try:
        res = requests.get(base_url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        date_links = [(a.get_text().strip(), a['href']) for a in soup.find_all('a', href=True) if a.get_text().strip().count('.') == 2]
        date_links.reverse() # Von alt nach neu
        
        neue_liste = []
        limit = 5 # Wir machen nur 5 pro Lauf, um absolut sicher zu gehen
        counter = 0

        for datum, link in date_links:
            day_url = link if link.startswith("http") else domain + link
            day_soup = BeautifulSoup(requests.get(day_url, headers=headers).text, 'html.parser')
            
            for case_link in day_soup.find_all('a', href=True):
                az = case_link.get_text().strip()
                if az.startswith("9C_") or az.startswith("8C_"):
                    if az in archiv:
                        zusammenfassung = archiv[az]
                    elif counter < limit:
                        print(f"Versuch {counter+1}: {az}")
                        full_link = case_link['href'] if case_link['href'].startswith("http") else domain + case_link['href']
                        case_page = requests.get(full_link, headers=headers)
                        case_text = BeautifulSoup(case_page.text, 'html.parser').get_text()
                        zusammenfassung = summarize_with_ai(case_text)
                        counter += 1
                        time.sleep(15)
                    else:
                        zusammenfassung = "Wird im nächsten Durchlauf analysiert..."

                    neue_liste.append({
                        "aktenzeichen": az,
                        "datum": datum,
                        "zusammenfassung": zusammenfassung,
                        "url": case_link['href'] if case_link['href'].startswith("http") else domain + case_link['href']
                    })

        neue_liste.reverse() # Neueste oben für die App
        
        with open('urteile.json', 'w', encoding='utf-8') as f:
            json.dump(neue_liste, f, ensure_ascii=False, indent=4)
            
    except Exception as e:
        print(f"Grober Fehler: {e}")

if __name__ == "__main__":
    scrape_bger()
