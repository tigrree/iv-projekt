import os
import requests
from datetime import datetime
from bs4 import BeautifulSoup

# AUTOMATISIERUNG: Manuelles Datum für den Text-Nachtrag
ZIEL_DATUM = "25.03.2026"

def scrape_bger():
    print(f"--- Nur-Text-Scan gestartet für: {ZIEL_DATUM} ---")
    domain = "https://www.bger.ch"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    # Ordner für Volltexte erstellen, falls nicht vorhanden
    if not os.path.exists('urteilstexte'):
        os.makedirs('urteilstexte')
        
    # HINWEIS: JSON-Laden und KI-Aufruf sind in diesem Skript deaktiviert!

    try:
        base_res = requests.get(f"{domain}/ext/eurospider/live/de/php/aza/http/index_aza.php?lang=de&mode=index", headers=headers)
        soup = BeautifulSoup(base_res.text, 'html.parser')
        tag_link = next((a['href'] for a in soup.find_all('a', href=True) if a.get_text().strip() == ZIEL_DATUM), None)
        
        if tag_link:
            full_tag_url = tag_link if tag_link.startswith("http") else domain + tag_link
            rows = BeautifulSoup(requests.get(full_tag_url, headers=headers).text, 'html.parser').find_all('tr')
            
            iv_keywords = ["invalid"]
            ak_keywords = [
                "familienzulage", "allocation familiale", "assegni familiari", 
                "hinterlassenenversicherung", "vieillesse", "vecchiaia", 
                "krankenversicherung", "maladie", "malattie", 
                "ergänzungsleistung", "prestations complémentaires", "prestazioni complementari"
            ]

            for i in range(len(rows)):
                row = rows[i]
                link_tag = row.find('a', href=True)
                if not link_tag: continue
                
                raw_az = link_tag.get_text().strip()
                if not (raw_az.startswith("9C_") or raw_az.startswith("8C_")): continue
                
                volltext = row.get_text(" ", strip=True)
                
                if i + 1 < len(rows):
                    next_row = rows[i+1]
                    if not next_row.find('a', href=True):
                        volltext += " " + next_row.get_text(" ", strip=True)
                
                search_text = volltext.lower()
                ist_iv = any(k in search_text for k in iv_keywords)
                ist_ak = any(k in search_text for k in ak_keywords)

                if ist_iv or ist_ak:
                    clean_az = raw_az.replace("*", "").strip()
                    case_url = link_tag['href'] if link_tag['href'].startswith("http") else domain + link_tag['href']
                    
                    # Volltext der Detailseite abrufen
                    case_soup = BeautifulSoup(requests.get(case_url, headers=headers).text, 'html.parser')
                    case_full_text = case_soup.get_text(separator='\n', strip=True)
                    
                    # --- Boilerplate (Header/Footer) wegschneiden ---
                    if "Tribunal federal" in case_full_text:
                        case_full_text = case_full_text.split("Tribunal federal", 1)[-1].strip()
                        
                    if "Navigation\nNeue Suche" in case_full_text:
                        case_full_text = case_full_text.split("Navigation\nNeue Suche", 1)[0].strip()
                    # ------------------------------------------------------
                    
                    # VOLLTEXT SPEICHERN FÜR DEN CHATBOT
                    safe_filename = clean_az.replace('/', '_')
                    with open(f'urteilstexte/{safe_filename}.txt', 'w', encoding='utf-8') as tf:
                        tf.write(case_full_text)
                    print(f"Text gespeichert: {safe_filename}.txt")
                    
        print(f"Scan für {ZIEL_DATUM} erfolgreich abgeschlossen. Keine JSON-Dateien wurden verändert.")
        
    except Exception as e: 
        print(f"Fataler Fehler beim Scraping: {e}")

if __name__ == "__main__":
    scrape_bger()
