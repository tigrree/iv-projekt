import requests
from bs4 import BeautifulSoup
import json
import os
import time
from datetime import datetime

# --- MANUELLE EINSTELLUNG ---
ZIEL_DATUM = "13.02.2026" 
# ----------------------------

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
KEYWORDS = ["invalid"]

def translate_preview(text):
    """Übersetzt die Vorschau ins Deutsche, falls sie in einer anderen Sprache vorliegt."""
    if not GROQ_API_KEY or not text: return text
    
    foreign_indicators = ["assurance", "invalidité", "impotent", "allocation", "rendita", "invalidità"]
    is_foreign = any(word in text.lower() for word in foreign_indicators)
    
    if not is_foreign and ("versicherung" in text.lower() or "rente" in text.lower()):
        return text

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": "Du bist ein Übersetzer für Schweizer Rechtsterminologie. Übersetze kurz und präzise ins Deutsche."},
            {"role": "user", "content": f"Übersetze diesen Begriff der Invalidenversicherung ins Deutsche (z.B. Invalidenrente, Hilflosenentschädigung etc.). Antworte NUR mit der Übersetzung ohne Punkt: {text}"}
        ],
        "temperature": 0.1 
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        return response.json()['choices'][0]['message']['content'].strip().replace('"', '')
    except:
        return text

def summarize_with_ai(urteil_text):
    if not GROQ_API_KEY: return "API Key fehlt."
    clean_text = " ".join(urteil_text.split()[:750])
    PROMPT_TEXT = """
Fasse das Urteil als Schweizer Jurist exakt in diesem Format zusammen:
**Sachverhalt & Anträge**\n[Hier Text einfügen]

**Streitig:**\n[Hier Text einfügen]

**Zu prüfen & Entscheidung:**\n[Hier Text einfügen]

Zwingend in Deutsch antworten. Keine Einleitung, nur dieser Block.
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
        return response.json()['choices'][0]['message']['content'].strip()
    except:
        return "Zusammenfassung aktuell nicht verfügbar."

def scrape_bger():
    print(f"--- Starte Präzisions-Scan für: {ZIEL_DATUM} ---")
    domain = "https://www.bger.ch"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    if not os.path.exists('urteile.json'):
        with open('urteile.json', 'w', encoding='utf-8') as f: json.dump([], f)
    with open('urteile.json', 'r', encoding='utf-8') as f:
        try:
            archiv_daten = json.load(f)
        except:
            archiv_daten = []

    try:
        base_res = requests.get(f"{domain}/ext/eurospider/live/de/php/aza/http/index_aza.php?lang=de&mode=index", headers=headers)
        soup = BeautifulSoup(base_res.text, 'html.parser')
        tag_link = next((a['href'] for a in soup.find_all('a', href=True) if a.get_text().strip() == ZIEL_DATUM), None)
        
        if not tag_link: return print(f"Datum {ZIEL_DATUM} noch nicht gelistet.")

        day_soup = BeautifulSoup(requests.get(tag_link if tag_link.startswith("http") else domain + tag_link, headers=headers).text, 'html.parser')
        tages_ergebnisse = []
        rows = day_soup.find_all('tr')
        
        for i in range(len(rows)):
            row = rows[i]
            link_tag = row.find('a', href=True)
            if not link_tag: continue
            
            az = link_tag.get_text().strip()
            if not (az.startswith("9C_") or az.startswith("8C_")): continue
            
            vorschau_text = ""
            if i + 1 < len(rows):
                potential_detail = rows[i+1].get_text().strip()
                if not (potential_detail.startswith("8C_") or potential_detail.startswith("9C_")):
                    vorschau_text = potential_detail
            
            if not vorschau_text:
                text_parts = [t.strip() for t in row.find_all(string=True) if t.strip()]
                try:
                    idx = text_parts.index(az)
                    if len(text_parts) > idx + 1: vorschau_text = text_parts[idx+1]
                except: pass

            full_context = row.get_text() + " " + (rows[i+1].get_text() if i+1 < len(rows) else "")
            if any(key in full_context.lower() for key in KEYWORDS):
                vorschau_deutsch = translate_preview(vorschau_text)
                print(f"Treffer: {az} | Vorschau: {vorschau_deutsch}")
                
                case_url = link_tag['href'] if link_tag['href'].startswith("http") else domain + link_tag['href']
                
                existing = next((d for d in archiv_daten if d['aktenzeichen'] == az), None)
                if existing and "nicht verfügbar" not in existing['zusammenfassung'] and existing['zusammenfassung'] != "":
                    zusammenfassung = existing['zusammenfassung']
                else:
                    print(f"Analysiere {az}...")
                    case_res = requests.get(case_url, headers=headers)
                    zusammenfassung = summarize_with_ai(BeautifulSoup(case_res.text, 'html.parser').get_text())
                    time.sleep(12)

                tages_ergebnisse.append({
                    "aktenzeichen": az, "datum": ZIEL_DATUM,
                    "vorschau": vorschau_deutsch, "zusammenfassung": zusammenfassung, 
                    "url": case_url
                })

        # Archiv-Logik
        archiv_daten = [d for d in archiv_daten if d['datum'] != ZIEL_DATUM]
        archiv_daten.extend(tages_ergebnisse)
        archiv_daten.sort(key=lambda x: datetime.strptime(x['datum'], "%d.%m.%Y"), reverse=True)
        
        # 14-Tage Limit
        alle_tage = sorted(list(set(d['datum'] for d in archiv_daten)), key=lambda x: datetime.strptime(x, "%d.%m.%Y"))
        if len(alle_tage) > 14:
            archiv_daten = [d for d in archiv_daten if d['datum'] != alle_tage[0]]

        with open('urteile.json', 'w', encoding='utf-8') as f:
            json.dump(archiv_daten, f, ensure_ascii=False, indent=4)
        print("Erfolg!")
            
    except Exception as e: print(f"Fehler: {e}")

if __name__ == "__main__":
    scrape_bger()
