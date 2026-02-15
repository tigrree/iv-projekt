import requests
from bs4 import BeautifulSoup
import json
import os
import time

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Strikt auf das Sachgebiet bezogene Keywords
IV_KEYWORDS = ["Invalidenversicherung", "Assurance-invalidité", "Assicurazione per l’invalidità", "Invalid"]

def summarize_with_ai(urteil_text):
    if not GROQ_API_KEY:
        return "Vorschau im Originalurteil verfügbar."
    
    words = urteil_text.split()
    clean_text = " ".join(words[:500])
    
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": f"Du bist Schweizer Jurist. Fasse dieses IV-Urteil in 3 prägnanten Sätzen zusammen (Sachverhalt, Rechtsfrage, Ergebnis): {clean_text}"}],
        "temperature": 0.1
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content'].strip()
    except Exception as e:
        print(f"KI Fehler: {e}")
        return "Zusammenfassung aktuell nicht verfügbar."

def scrape_bger():
    base_url = "https://www.bger.ch/ext/eurospider/live/de/php/aza/http/index_aza.php?lang=de&mode=index"
    domain = "https://www.bger.ch"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    # Archiv laden (Gedächtnis)
    archiv = {}
    if os.path.exists('urteile.json'):
        try:
            with open('urteile.json', 'r', encoding='utf-8') as f:
                alte_daten = json.load(f)
                # Wir behalten nur echte Zusammenfassungen im Archiv
                archiv = {d['aktenzeichen']: d['zusammenfassung'] for d in alte_daten 
                          if len(d['zusammenfassung']) > 50 and "verfügbar" not in d['zusammenfassung']}
        except: pass

    try:
        res = requests.get(base_url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        # Die aktuellsten Tage (Index-Seite)
        date_links = [(a.get_text().strip(), a['href']) for a in soup.find_all('a', href=True) if a.get_text().strip().count('.') == 2][:20]
        
        neue_liste = []
        limit = 50 # Erhöhtes Limit, damit keine Urteile wie 8C_401/2025 vergessen werden
        ai_counter = 0

        for datum, link in date_links:
            day_url = link if link.startswith("http") else domain + link
            day_res = requests.get(day_url, headers=headers)
            day_soup = BeautifulSoup(day_res.text, 'html.parser')
            
            iv_urteil_an_diesem_tag = False
            tages_entscheide = []
            
            for case_link in day_soup.find_all('a', href=True):
                az = case_link.get_text().strip()
                # Fokus auf 8C und 9C (Sozialversicherungsrechtliche Abteilungen)
                if az.startswith("9C_") or az.startswith("8C_"):
                    full_link = case_link['href'] if case_link['href'].startswith("http") else domain + case_link['href']
                    
                    try:
                        case_res = requests.get(full_link, headers=headers)
                        case_soup = BeautifulSoup(case_res.text, 'html.parser')
                        
                        # STRATEGIE: Wir suchen NUR im Header (den ersten 800 Zeichen des Textes)
                        # Dort stehen Aktenzeichen, Parteien und das Sachgebiet.
                        header_text = case_soup.get_text()[:800]
                        
                        # Filter: Nur wenn eines der Keywords im Header vorkommt
                        if any(kw.lower() in header_text.lower() for kw in IV_KEYWORDS):
                            iv_urteil_an_diesem_tag = True
                            
                            if az in archiv:
                                zusammenfassung = archiv[az]
                            elif ai_counter < limit:
                                print(f"Analysiere neues IV-Urteil: {az}")
                                zusammenfassung = summarize_with_ai(case_soup.get_text())
                                ai_counter += 1
                                time.sleep(1) # Kurze Pause für API
                            else:
                                zusammenfassung = "Wird im nächsten Durchlauf analysiert..."

                            tages_entscheide.append({
                                "aktenzeichen": az,
                                "datum": datum,
                                "zusammenfassung": zusammenfassung,
                                "url": full_link
                            })
                    except Exception as e:
                        print(f"Fehler bei {az}: {e}")
                        continue
            
            if iv_urteil_an_diesem_tag:
                neue_liste.extend(tages_entscheide)
            else:
                # Dummy-Eintrag für leere Tage
                neue_liste.append({
                    "aktenzeichen": "Info",
                    "datum": datum,
                    "zusammenfassung": "An diesem Tag wurden keine IV-relevanten Urteile publiziert.",
                    "url": None
                })

        # Speichern der Ergebnisse
        with open('urteile.json', 'w', encoding='utf-8') as f:
            json.dump(neue_liste, f, ensure_ascii=False, indent=4)
            
        print(f"Scraping beendet. {len(neue_liste)} Einträge gespeichert.")
            
    except Exception as e:
        print(f"Fehler im Hauptablauf: {e}")

if __name__ == "__main__":
    scrape_bger()
