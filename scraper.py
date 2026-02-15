import requests
from bs4 import BeautifulSoup
import json
import os
import time

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Keywords für die Suche im Sachgebiet
IV_KEYWORDS = ["Invalidenversicherung", "Assurance-invalidité", "Assicurazione per l’invalidità", "Invalid"]

def summarize_with_ai(urteil_text):
    if not GROQ_API_KEY:
        return "Vorschau im Originalurteil verfügbar."
    
    # Wir nehmen die ersten 600 Wörter für die KI, um den Kontext zu wahren
    words = urteil_text.split()
    clean_text = " ".join(words[:600])
    
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": f"Du bist Schweizer Jurist. Fasse dieses IV-Urteil in 3 prägnanten Sätzen zusammen (Sachverhalt, Rechtsfrage, Ergebnis): {clean_text}"}],
        "temperature": 0.1
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=40) # Timeout erhöht
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
                archiv = {d['aktenzeichen']: d['zusammenfassung'] for d in alte_daten 
                          if len(d['zusammenfassung']) > 50 and "verfügbar" not in d['zusammenfassung'] 
                          and d['aktenzeichen'] != "Info"}
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
            
            iv_urteil_an_diesem_tag = False
            tages_entscheide = []
            
            for case_link in day_soup.find_all('a', href=True):
                az = case_link.get_text().strip()
                if az.startswith("9C_") or az.startswith("8C_"):
                    full_link = case_link['href'] if case_link['href'].startswith("http") else domain + case_link['href']
                    
                    try:
                        case_res = requests.get(full_link, headers=headers)
                        case_soup = BeautifulSoup(case_res.text, 'html.parser')
                        
                        # NEU: Wir suchen im gesamten Text, aber NUR in den ersten 3000 Zeichen (Header-Bereich)
                        # Das ist sicher genug, um das Sachgebiet zu finden, aber schließt Kostenfolgen aus.
                        full_text = case_soup.get_text()
                        header_check_area = full_text[:3000] 
                        
                        is_iv = any(kw.lower() in header_check_area.lower() for kw in IV_KEYWORDS)
                        
                        if is_iv:
                            iv_urteil_an_diesem_tag = True
                            if az in archiv:
                                zusammenfassung = archiv[az]
                            elif ai_counter < limit:
                                print(f"Analysiere: {az}")
                                zusammenfassung = summarize_with_ai(full_text)
                                ai_counter += 1
                                time.sleep(12) # Erhöhte Pause für API Stabilität
                            else:
                                zusammenfassung = "Wird im nächsten Durchlauf analysiert..."

                            tages_entscheide.append({
                                "aktenzeichen": az,
                                "datum": datum,
                                "zusammenfassung": zusammenfassung,
                                "url": full_link
                            })
                    except: continue
            
            if iv_urteil_an_diesem_tag:
                neue_liste.extend(tages_entscheide)
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
