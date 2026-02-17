import requests
from bs4 import BeautifulSoup
import json
import os
import time
from datetime import datetime

# --- DEINE MANUELLE EINSTELLUNG ---
ZIEL_DATUM = "11.02.2026"
# ----------------------------------

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Extrem reduzierte Keywords für maximale Trefferrate
KEYWORDS = ["invalid", "iv-stelle", "office ai", "ufficio ai", "ai"]

def summarize_with_ai(urteil_text):
    if not GROQ_API_KEY: return "API Key fehlt."
    clean_text = " ".join(urteil_text.split()[:750])
    PROMPT_TEXT = "Fasse das Urteil als Schweizer Jurist zusammen: **Sachverhalt & Anträge**, **Streitig**, **Zu prüfen & Entscheidung**. Zwingend Deutsch."
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": PROMPT_TEXT + clean_text}], "temperature": 0.1}
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        return response.json()['choices'][0]['message']['content'].strip()
    except: return "Zusammenfassung aktuell nicht verfügbar."

def scrape_bger():
    print(f"--- Starte ULTIMATIVEN Scan für: {ZIEL_DATUM} ---")
    domain = "https://www.bger.ch"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    archiv_daten = []
    archiv_map = {} 
    if os.path.exists('urteile.json'):
        with open('urteile.json', 'r', encoding='utf-8') as f:
            try:
                archiv_daten = json.load(f)
                for d in archiv_daten: archiv_map[d['aktenzeichen']] = d['zusammenfassung']
            except: pass

    try:
        base_res = requests.get(f"{domain}/ext/eurospider/live/de/php/aza/http/index_aza.php?lang=de&mode=index", headers=headers)
        soup = BeautifulSoup(base_res.text, 'html.parser')
        tag_link = next((a['href'] for a in soup.find_all('a', href=True) if a.get_text().strip() == ZIEL_DATUM), None)
        
        if not tag_link: return print("Datum nicht gefunden.")

        day_url = tag_link if tag_link.startswith("http") else domain + tag_link
        day_res = requests.get(day_url, headers=headers)
        day_soup = BeautifulSoup(day_res.text, 'html.parser')
        tages_ergebnisse = []
        
        # Wir suchen jetzt einfach nach JEDEM Link, der nach einem Aktenzeichen aussieht
        all_links = day_soup.find_all('a', href=True)
        
        for link in all_links:
            az = link.get_text().strip()
            # Nur 8C und 9C Aktenzeichen beachten
            if not (az.startswith("9C_") or az.startswith("8C_")): continue
            
            # Jetzt schauen wir uns das "Umfeld" dieses Links an (die ganze Zeile im Browser)
            # Wir nehmen den Text des Elternelements (die Tabellenzeile)
            parent_row = link.find_parent('tr')
            if not parent_row: continue
            
            # DER TRICK: Wir nehmen den Text der aktuellen Zeile UND der direkt folgenden Zeile
            # falls das BGer dort den Zusatz-Text versteckt hat.
            row_index = parent_row.parent.contents.index(parent_row)
            try:
                next_row_text = parent_row.parent.contents[row_index + 1].get_text()
            except:
                next_row_text = ""
                
            combined_context = (parent_row.get_text() + " " + next_row_text).lower()
            
            # Prüfung auf Keywords
            if any(key in combined_context for key in KEYWORDS):
                full_link = link['href'] if link['href'].startswith("http") else domain + link['href']
                
                if az in archiv_map and "nicht verfügbar" not in archiv_map[az]:
                    print(f"Überspringe (bereits da): {az}")
                    zusammenfassung = archiv_map[az]
                else:
                    print(f"!!! TREFFER: {az} !!!")
                    case_text = BeautifulSoup(requests.get(full_link, headers=headers).text, 'html.parser').get_text()
                    zusammenfassung = summarize_with_ai(case_text)
                    time.sleep(10)
                
                # Doubletten im aktuellen Durchlauf vermeiden
                if not any(e['aktenzeichen'] == az for e in tages_ergebnisse):
                    tages_ergebnisse.append({"aktenzeichen": az, "datum": ZIEL_DATUM, "zusammenfassung": zusammenfassung, "url": full_link})

        if not tages_ergebnisse:
            tages_ergebnisse.append({"aktenzeichen": "Info", "datum": ZIEL_DATUM, "zusammenfassung": "Keine IV-Urteile.", "url": domain})

        archiv_daten = [d for d in archiv_daten if d['datum'] != ZIEL_DATUM]
        archiv_daten.extend(tages_ergebnisse)
        archiv_daten.sort(key=lambda x: datetime.strptime(x['datum'], "%d.%m.%Y"), reverse=True)

        with open('urteile.json', 'w', encoding='utf-8') as f:
            json.dump(archiv_daten, f, ensure_ascii=False, indent=4)
        print("Erfolg!")
            
    except Exception as e: print(f"Fehler: {e}")

if __name__ == "__main__":
    scrape_bger()
