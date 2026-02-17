import requests
from bs4 import BeautifulSoup
import json
import os
import time
from datetime import datetime

# --- DEINE MANUELLE EINSTELLUNG ---
ZIEL_DATUM = "11.02.2026"  # Hier das gewünschte Datum eintragen
# ----------------------------------

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# --- DEINE OPTIMIERTE KEYWORD-LISTE ---
KEYWORDS = [
    "invalidenversicherung", 
    "invalidenrente", 
    "assurance-invalidité", 
    "rente d'invalidité", 
    "assicurazione per l’invalidità", 
    "rendita d'invalidità",
    "iv-stelle",
    "office ai",
    "ufficio ai"
]

def summarize_with_ai(urteil_text):
    if not GROQ_API_KEY: 
        return "API Key fehlt."
    
    # Kürzen des Textes auf ca. 750 Wörter, um Token-Limits (70b Modell) zu schonen
    clean_text = " ".join(urteil_text.split()[:750])
    
    PROMPT_TEXT = """
Fasse das Urteil als Schweizer Jurist exakt so zusammen:
**Sachverhalt & Anträge:** [Text]
**Streitig:** [Kern des Streits & anwendbares Recht (altes Recht vor 2022 / neues Recht)]
**Zu prüfen & Entscheidung:** [Begründung & Ergebnis]
Zwingend in Deutsch antworten.
"""
    
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": PROMPT_TEXT + clean_text}],
        "temperature": 0.1 
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        if response.status_code == 429: 
            return "Zusammenfassung aktuell nicht verfügbar (Rate Limit)."
        return response.json()['choices'][0]['message']['content'].strip()
    except Exception:
        return "Zusammenfassung aktuell nicht verfügbar."

def scrape_bger():
    print(f"--- Starte gezielte Analyse für Tag: {ZIEL_DATUM} ---")
    base_url = "https://www.bger.ch/ext/eurospider/live/de/php/aza/http/index_aza.php?lang=de&mode=index"
    domain = "https://www.bger.ch"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    # 1. Archiv laden & Stand prüfen
    archiv_daten = []
    archiv_map = {} 
    if os.path.exists('urteile.json'):
        with open('urteile.json', 'r', encoding='utf-8') as f:
            try:
                archiv_daten = json.load(f)
                for d in archiv_daten:
                    # Map erstellen, um zu wissen, was wir schon haben
                    archiv_map[d['aktenzeichen']] = d['zusammenfassung']
            except:
                archiv_daten = []

    try:
        res = requests.get(base_url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        tag_link = None
        for a in soup.find_all('a', href=True):
            if a.get_text().strip() == ZIEL_DATUM:
                tag_link = a['href']
                break
        
        if not tag_link:
            print(f"Datum {ZIEL_DATUM} wurde auf der BGer-Seite nicht gefunden.")
            return

        # 2. Den Tag scannen
        day_url = tag_link if tag_link.startswith("http") else domain + tag_link
        day_res = requests.get(day_url, headers=headers)
        day_soup = BeautifulSoup(day_res.text, 'html.parser')
        tages_ergebnisse = []
        
        rows = day_soup.find_all('tr')
        print(f"Gefundene Zeilen am {ZIEL_DATUM}: {len(rows)}")

        for row in rows:
            row_text_lower = row.get_text().lower()
            
            # Filter: Keywords + Abteilungen 8C/9C
            treffer = any(key in row_text_lower for key in KEYWORDS)
            
            if treffer:
