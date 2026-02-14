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
    
    # Text-Vorbereitung: max 400 Wörter für eine stabile API-Antwort
    words = urteil_text.split()
    clean_text = " ".join(words[:400])
    
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Hier wurde das Modell auf das neue llama-3.3-70b-versatile aktualisiert
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "user", "content": f"Fasse kurz in 3 Saetzen auf Deutsch zusammen: {clean_text}"}
        ],
        "temperature": 0.1
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 429:
            print("Rate Limit erreicht. Warte 30 Sek...")
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
    
    # Vorhandene Daten laden (Gedächtnis)
    archiv = {}
    if os.path.exists('urteile.json'):
        try:
            with open('urteile.json', 'r', encoding='utf-8') as f:
                alte_daten = json.load(f)
                # Wir behalten nur Urteile, die bereits eine ECHTE Zusammenfassung haben
                archiv = {d['aktenzeichen']: d['zusammenfassung'] for d in alte_daten 
                          if len(d['zusammenfassung']) > 50 and "verfügbar" not in d['zusammenfassung']}
        except: pass

    try:
        res = requests.get(base_url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        date_links = [(a.get_text().strip(), a['href']) for a in soup.find_all('a', href=True) if a.get_text().strip().count('.') == 2]
        
        # Chronologisch von alt (27.01.) nach neu
        date_links.reverse() 
        
        neue_liste = []
        limit = 6 # Wir verarbeiten 6 Urteile pro Lauf
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
                        full_link = case_
