import requests
from bs4 import BeautifulSoup
import json
import os
import time

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

IV_KEYWORDS = ["Invalidenversicherung", "Assurance-invalidité", "Assicurazione per l’invalidità", "Invalid", "Invalidité", "Invalidità"]

def summarize_with_ai(urteil_text, retries=3):
    if not GROQ_API_KEY: return "Vorschau im Originalurteil verfügbar."
    
    words = urteil_text.split()
    clean_text = " ".join(words[:500]) # Etwas kürzerer Text für stabilere API-Antworten
    
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": f"Fasse dieses Schweizer IV-Urteil in 3 Sätzen zusammen (Sachverhalt, Rechtsfrage, Ergebnis): {clean_text}"}],
        "temperature": 0.1
    }
    
    for i in range(retries):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=40)
            if response.status_code == 429: # Rate Limit
                wait = (i + 1) * 40
                print(f"Rate Limit! Warte {wait}s...")
                time.sleep(wait)
                continue
            response.raise_for_status()
            return response.json()['choices'][0]['message']['content'].strip()
        except:
            time.sleep(10)
    return "Zusammenfassung aktuell nicht verfügbar."

def scrape_bger():
    base_url = "https://www.bger.ch/ext/eurospider/live/de/php/aza/http/index_aza.php?lang=de&mode=index"
    domain = "https://www.bger.ch"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    archiv = {}
    if os.path.exists('urteile.json'):
        try:
            with open('urteile.json', 'r', encoding='utf-8') as f:
                alte_daten = json.load(f)
                # WICHTIG: Wir archivieren nur, wenn die Zusammenfassung ECHT ist (kein Fehlertext)
                for d in alte_daten:
                    if d['aktenzeichen'] != "Info" and "nicht verfügbar" not in d['zusammenfassung'] and len(d['zusammenfassung']) > 40:
                        archiv[d['aktenzeichen']] = d['zusammenfassung']
        except: pass

    try:
        res = requests.get(base_url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        date_links = [(a.get_text().strip(), a['href']) for a in soup.find_all('a', href=True) if a.get_text().strip().count('.') == 2][:20]
        
        neue_liste = []
        ai_limit = 12 # Pro Durchlauf max 12 neue Urteile, um API-Sperren zu vermeiden
        ai_counter = 0

        for datum, link in date_links:
            day_url = link if link.startswith("http") else domain + link
            day_soup = BeautifulSoup(requests.get(day_url, headers=headers).text, 'html.parser')
            tages_ergebnisse = []
            
            for row in day_soup.find_all('tr'):
                link_tag = row.find('a', href=True)
                if not link_tag: continue
                az = link_tag.get_text().strip()
                if not (az.startswith("9C_") or az.startswith("8C_")): continue
                
                row_text = row.get_text().lower()
                if any(kw.lower() in row_text for kw in IV_KEYWORDS):
                    full_link = link_tag['href'] if link_tag['href'].startswith("http") else domain + link_tag['href']
                    
                    if az in archiv:
                        zusammenfassung = archiv[az]
                    elif ai_counter < ai_limit:
                        print(f"Analysiere: {az}...")
                        case_res = requests.get(full_link, headers=headers)
                        case_text = BeautifulSoup(case_res.text, 'html.parser').get_text()
                        zusammenfassung = summarize_with_ai(case_text)
                        ai_counter += 1
                        time.sleep(25) # Lange Pause für API-Stabilität
                    else:
                        zusammenfassung = "Zusammenfassung aktuell nicht verfügbar."

                    tages_ergebnisse.append({"aktenzeichen": az, "datum": datum, "zusammenfassung": zusammenfassung, "url": full_link})
            
            if tages_ergebnisse: neue_liste.extend(tages_ergebnisse)
            else: neue_liste.append({"aktenzeichen": "Info", "datum": datum, "zusammenfassung": "An diesem Tag wurden keine IV-relevanten Urteile publiziert.", "url": "https://www.bger.ch"})

        with open('urteile.json', 'w', encoding='utf-8') as f:
            json.dump(neue_liste, f, ensure_ascii=False, indent=4)
            
    except Exception as e:
        print(f"Fehler: {e}")

if __name__ == "__main__":
    scrape_bger()
