import requests
from bs4 import BeautifulSoup
import json
import os
import time

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
IV_KEYWORDS = ["Invalidenversicherung", "Assurance-invalidité", "Assicurazione per l’invalidità", "Invalid"]

def summarize_with_ai(urteil_text):
    if not GROQ_API_KEY: return "Vorschau im Originalurteil verfügbar."
    words = urteil_text.split()
    clean_text = " ".join(words[:600])
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": f"Fasse dieses IV-Urteil in 3 Sätzen zusammen: {clean_text}"}],
        "temperature": 0.1
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=40)
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content'].strip()
    except: return "Zusammenfassung aktuell nicht verfügbar."

def scrape_bger():
    base_url = "https://www.bger.ch/ext/eurospider/live/de/php/aza/http/index_aza.php?lang=de&mode=index"
    domain = "https://www.bger.ch"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    archiv = {}
    if os.path.exists('urteile.json'):
        try:
            with open('urteile.json', 'r', encoding='utf-8') as f:
                alte_daten = json.load(f)
                archiv = {d['aktenzeichen']: d['zusammenfassung'] for d in alte_daten 
                          if d['aktenzeichen'] != "Info" and "verfügbar" not in d['zusammenfassung']}
        except: pass

    try:
        res = requests.get(base_url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        date_links = [(a.get_text().strip(), a['href']) for a in soup.find_all('a', href=True) if a.get_text().strip().count('.') == 2][:20]
        
        neue_liste = []
        limit = 50
        ai_counter = 0

        for datum, link in date_links:
            day_url = link if link.startswith("http") else domain + link
            day_soup = BeautifulSoup(requests.get(day_url, headers=headers).text, 'html.parser')
            
            tages_ergebnisse = []
            
            # Suche die Tabelle mit den Entscheiden
            table = day_soup.find('table')
            if not table: continue

            rows = table.find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                # Wir suchen nach der Zeile, die das Aktenzeichen (z.B. 9C_...) enthält
                if len(cols) >= 2:
                    az_cell = row.find('a', href=True)
                    if not az_cell: continue
                    
                    az = az_cell.get_text().strip()
                    if not (az.startswith("9C_") or az.startswith("8C_")): continue
                    
                    # Suche in der gesamten Zeile nach den IV-Keywords im Text (Sachgebiet-Spalte)
                    row_text = row.get_text()
                    
                    if any(kw.lower() in row_text.lower() for kw in IV_KEYWORDS):
                        full_link = az_cell['href'] if az_cell['href'].startswith("http") else domain + az_cell['href']
                        
                        if az in archiv:
                            zusammenfassung = archiv[az]
                        elif ai_counter < limit:
                            print(f"Analysiere IV-Urteil: {az}")
                            case_res = requests.get(full_link, headers=headers)
                            case_text = BeautifulSoup(case_res.text, 'html.parser').get_text()
                            zusammenfassung = summarize_with_ai(case_text)
                            ai_counter += 1
                            time.sleep(12)
                        else:
                            zusammenfassung = "Wird analysiert..."

                        tages_ergebnisse.append({
                            "aktenzeichen": az,
                            "datum": datum,
                            "zusammenfassung": zusammenfassung,
                            "url": full_link
                        })
            
            if tages_ergebnisse:
                neue_liste.extend(tages_ergebnisse)
            else:
                neue_liste.append({
                    "aktenzeichen": "Info",
                    "datum": datum,
                    "zusammenfassung": "An diesem Tag wurden keine IV-relevanten Urteile publiziert.",
                    "url": "https://www.bger.ch"
                })

        with open('urteile.json', 'w', encoding='utf-8') as f:
            json.dump(neue_liste, f, ensure_ascii=False, indent=4)
            
    except Exception as e:
        print(f"Fehler: {e}")

if __name__ == "__main__":
    scrape_bger()
