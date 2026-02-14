import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime

# Wir holen den Key sicher aus den GitHub Secrets
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

def summarize_with_ai(urteil_text):
    if not GROQ_API_KEY:
        return "Zusammenfassung aktuell nicht verfügbar (API Key fehlt)."
    
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Der Prompt: Wir sagen der KI genau, was sie tun soll
    prompt = f"""Du bist ein spezialisierter Jurist für Schweizer Sozialversicherungsrecht. 
    Fasse das folgende Urteil zur Invalidenversicherung (IV) in maximal 3-4 Sätzen zusammen.
    Konzentriere dich auf: 1. Sachverhalt, 2. Die entscheidende Rechtsfrage, 3. Das Ergebnis (Gutgeheissen/Abgewiesen).
    
    Text des Urteils:
    {urteil_text[:4000]}""" # Wir senden die ersten 4000 Zeichen (reicht für das Wesentliche)

    data = {
        "model": "llama3-8b-8192", # Ein sehr schnelles und kostenloses Modell
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3 # Niedrige Temperatur für sachliche Antworten
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=15)
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content'].strip()
    except Exception as e:
        print(f"KI Fehler: {e}")
        return "Zusammenfassung konnte nicht generiert werden. Bitte Originalurteil prüfen."

def scrape_bger():
    base_url = "https://www.bger.ch/ext/eurospider/live/de/php/aza/http/index_aza.php?lang=de&mode=index"
    domain = "https://www.bger.ch"
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
    
    alle_entscheide = []
    heute = datetime.now()
    heute_str = heute.strftime("%d.%m.%Y")
    wochentag = heute.weekday() 

    try:
        response = requests.get(base_url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Datums-Links finden
        date_links = []
        for a in soup.find_all('a', href=True):
            if a.get_text().strip().count('.') == 2:
                date_links.append((a.get_text().strip(), a['href']))

        gefunden_fuer_heute = False

        # Nur die neuesten Tage bearbeiten (um API-Limits zu sparen und Zeit zu gewinnen)
        # Wir nehmen hier die ersten 14 Einträge der Liste
        for datum, link in date_links[:14]:
            day_url = link if link.startswith("http") else domain + link
            day_res = requests.get(day_url, headers=headers, timeout=10)
            day_soup = BeautifulSoup(day_res.text, 'html.parser')
            
            for case_link in day_soup.find_all('a', href=True):
                case_text = case_link.get_text().strip()
                if case_text.startswith("9C_") or case_text.startswith("8C_"):
                    full_link = case_link['href'] if case_link['href'].startswith("http") else domain + case_link['href']
                    
                    # JETZT: Den Text des Urteils für die KI laden
                    try:
                        case_page = requests.get(full_link, headers=headers, timeout=10)
                        case_content = BeautifulSoup(case_page.text, 'html.parser').get_text()
                        # KI-Zusammenfassung erstellen
                        zusammenfassung = summarize_with_ai(case_content)
                    except:
                        zusammenfassung = "Details im Originalurteil verfügbar."

                    alle_entscheide.append({
                        "aktenzeichen": case_text,
                        "datum": datum,
                        "zusammenfassung": zusammenfassung,
                        "url": full_link
                    })
                    if datum == heute_str:
                        gefunden_fuer_heute = True

        if not gefunden_fuer_heute and wochentag < 5:
            alle_entscheide.insert(0, {
                "aktenzeichen": "Info",
                "datum": heute_str,
                "zusammenfassung": "Heute wurden keine neuen IV-relevanten Urteile publiziert.",
                "url": None
            })

    except Exception as e:
        alle_entscheide = [{"aktenzeichen": "Fehler", "datum": heute_str, "zusammenfassung": str(e), "url": None}]

    with open('urteile.json', 'w', encoding='utf-8') as f:
        json.dump(alle_entscheide, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    scrape_bger()
