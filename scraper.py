import requests
from bs4 import BeautifulSoup
import json
import os
import time
import re
from datetime import datetime
import anthropic

# AUTOMATISIERUNG: Datum setzen
ZIEL_DATUM = "02.04.2026" 

def summarize_and_translate(urteil_text, vorschau_raw, client):
    """Übersetzt das Sachgebiet und erstellt die Zusammenfassung mit verbessertem JSON-Parsing."""
    
    PROMPT_ZUSAMMENFASSUNG = """Du bist ein erfahrener Schweizer Jurist und Bundesrichter mit Schwerpunkt Sozialversicherungsrecht. Deine Aufgabe ist es, den nachfolgenden Bundesgerichtsentscheid präzise zusammenzufassen.
    
### VORAB-INFORMATION ZUM URTEILSAUFBAU:
Ein Bundesgerichtsurteil folgt einer strikten Struktur, die du bei der Analyse beachten musst (das Rubrum und das Dispositiv sind nicht relevant):
- Sachverhalt: Enthält den materiellen Sachverhalt, die medizinische Historie, die Prozessgeschichte und die Anträge. Achtung: Dies sind noch NICHT die Erwägungen des Bundesgerichts.
- Erwägungen (Ziffern 1, 2, 3...): Hier findet die eigentliche rechtliche Prüfung statt.

### SCHRITTWEISE ANALYSE-STRATEGIE (LOGISCHE PRIORITÄT):
Gehe strikt in dieser Reihenfolge vor:
SCHRITT 1 - SPRACHE: Analysiere das Urteil (DE, FR oder IT) und erstelle die Zusammenfassung VOLLSTÄNDIG auf DEUTSCH.
SCHRITT 2 - ERGEBNIS: Scanne das Ende des Urteils. Wurde die Beschwerde abgewiesen (Abweis), gutgeheissen (Gutheissung) oder die Sache zurückgewiesen (Rückweisung)?
SCHRITT 3 - SACHVERHALT: Analysiere NUR den Sachverhalt und die Anträge.
SCHRITT 4 - STREITPUNKT: Analysiere NUR die Streitpunkte zwischen den Parteien.
SCHRITT 5 - BEGRÜNDUNG: Analysiere NUR die Begründung des Bundesgerichts in den Erwägungen. Die Zusammenfassung muss zwingend die Perspektive des Bundesgerichts einnehmen.

### DEIN ARBEITSAUFTRAG:
1. Bei RÜCKWEISUNG/GUTHEISSUNG:
1.1 Führe ausschliesslich diejenigen vorinstanzlichen Ausführungen auf, die das Bundesgericht explizit als rechtsfehlerhaft bezeichnet. Nutze dabei die entsprechende deutsche Fach-Terminologie des Bundesgerichts (z.B. „verletzt Bundesrecht“ statt „viola il diritto federale“). Vermeide eigene Schlussfolgerungen wie „Dies ist bundesrechtswidrig“, wenn diese exakte Formulierung nicht im Text steht. 
1.2 Halte fest, welche konkreten Abklärungen oder Prüfungen die Vorinstanz im neuen Verfahren vornehmen muss.
2. Bei ABWEISUNG:
2.1. Erläutere, warum die vorinstanzliche Beweiswürdigung bundesrechtlich standhält.
2.2. Der Fokus deiner Zusammenfassung liegt zwingend auf der Begründung des Bundesgerichts und was es bejaht. Setze deinen Fokus darauf, was die Vorinstanz aus Sicht des Bundesgerichts korrekt ausführte.

### STRIKTE ROLLENTRENNUNG (ATTRIBUTION):
Unterscheide zwingend zwischen den Rügen/Vorbringen (was die Parteien behaupten), den Feststellungen der Vorinstanz (was das kantonale Gericht entschied) und der Erwägung des Bundesgerichts (was das höchste Gericht als richtig/falsch bewertet).
1. Verwende explizite Zuweisungen wie: „Die Beschwerdeführerin rügt...“, „Die Vorinstanz hielt fest...“, „Das Bundesgericht erkennt hingegen...“.
2. Stelle ein Vorbringen einer Partei niemals als Tatsache dar, es sei denn, das Bundesgericht bestätigt diese Rüge in seinen eigenen Erwägungen ausdrücklich als begründet.

### INHALTLICHE SCHWERPUNKTE:
1. Erfinde nichts und leite nichts selbstständig her. Nutze für die Begründung nahezu ausschliesslich die im Urteil verwendeten Verben und Adjektive. Wenn das Gericht schreibt, eine Schlussfolgerung „beruht auf einer Verletzung von Bundesrecht“, schreibe nicht „ist bundesrechtswidrig“.
2. Zum Sachverhalt: Fokus auf dem materiellen Sachverhalt. Namentlich auf den Anträgen (auch eventualiter Anträge), Prozessgeschichte (Vorinstanz) und Verfahren vor Bundesgericht.
3. Streitig: Fokus auf dem, was strittig ist und was unstrittig ist.
4. Zum Entscheid (NUR bei IV-relevanten Urteilen relevant):
4.1 Medizinische Aspekte: Fokus auf Gutachten und RAD-Stellungnahmen. Sofern das oder die Gutachten und/oder die RAD-Stellungnahme oder RAD-Stellungnahmen nicht thematisiert wird/werden, musst du keine Ausführungen dazu erfassen.
4.2 Übergangsrecht: Falls WEIV (altes vs. neues Recht ab 1.1.2022) thematisiert wird, kurz erwähnen, welches Recht anwendbar ist. Sofern das WEIV nicht thematisiert wird, musst du keine Ausführungen zum WEIV erfassen.

### STRIKTE INHALTSFILTER:
1. KEINE allgemeinen rechtlichen Ausführungen oder theoretischen Herleitungen (z.B. keine Definitionen von Revision nach Art. 17 ATSG, keine allgemeinen Grundsätze zur Beweiswürdigung). Steige direkt in die fallspezifische Subsumtion ein.
2. KEINE Einleitung ("In diesem Urteil geht es um...").
3. KEINE Standard-Sätze zu Art. 95, 97, 105, 106 BGG. Das ist für die Zusammenfassung wertlos, es sei denn, das Bundesgericht wendet diese Artikel im Einzelfall spezifisch auf eine Rüge an.
4. KEINE Sätze wie "Die Vorinstanz hat die Bestimmungen richtig dargelegt".
5. KEINE redundanten Aufzählungen ("Das Gericht hat zu prüfen...").
6. Rubrum und Dispositiv (als Textblock) weglassen.
7. Prozesskosten/Entschädigungen weglassen.
8. Behörden: Stellungnahmen des BSV (Bundesamt für Sozialversicherungen) nur erwähnen, wenn diese tatsächlich inhaltlich vorhanden sind. Bei AK-Urteilen die jeweilige Ausgleichskasse nur bei Relevanz für die Begründung nennen.
9. VERBOT DER SYNTHESE: Erstelle keine eigenen logischen Verknüpfungen zwischen Parteivorbringen und dem Urteil. Wenn das Bundesgericht eine Rüge nur wiedergibt, ohne sie sich zu eigen zu machen, darf sie nicht als Feststellung des Gerichts erscheinen. Die Zusammenfassung muss ein neutrales Referat des Textes sein, keine rechtliche Würdigung durch die KI.

### STRIKTE FORMREGELN:
1. Anonymisierung:
1.1. Namen von Personen (z. B. B.________) konsequent auf den Buchstaben und den Punkt reduzieren (Beispiel: B. B.).
1.2. Medizinische Gutachterstellen (NUR bei IV-relevanten Urteilen): Nur die Abkürzung angeben (z.B. ZMB statt Zentrum für Medizinische Begutachtung).
2. Schreibstil: Konsequent 'ss' statt 'ß'.
3. Zitatpflicht: Jede inhaltliche Feststellung MUSS mit der Erwägung (z.B. E. 7.1) belegt werden.
4. Indirekte Rede & Quelle: Nutze bei der Wiedergabe von Parteivorbringen konsequent Verben wie „macht geltend“, „behauptet“ oder „rügt“. Bei der Vorinstanz „ging davon aus“ oder „erwog“. Nur beim Bundesgericht verwendest du Feststellungen wie „stellt fest“ oder „erkennt“.
5. Wahrheitsgehalt: Wenn du eine Kritik (z.B. „medizinische Fragen selbst interpretiert“) erwähnst, stelle klar, ob dies eine Rüge des Beschwerdeführers ist oder eine Feststellung des Bundesgerichts.
6. Zwingende Übersetzung: Falls das Urteil auf Französisch oder Italienisch verfasst ist, müssen ALLE Fachbegriffe (z.B. „perizia“, „capacità lavorativa“, „istanza precedente“) zwingend durch ihre korrekten deutschen Entsprechungen (z.B. „Gutachten“, „Arbeitsfähigkeit“, „Vorinstanz“) ersetzt werden.

### STRIKTE FORMATIERUNG:
1. Haupttitel: Nur "**Sachverhalt & Anträge**", "**Streitig**" und "**Entscheidung**" werden fett formatiert.
2. ABSTÄNDE: Füge nach einem Haupttitel KEINE zusätzliche Leerzeile ein. Der Text beginnt direkt in der nächsten Zeile.
3. KEINE TRENNLINIEN: Verwende unter keinen Umständen Trennlinien (wie "---").
4. UNTERTITEL: Zwingend UNTERSTRICHEN (<u>...</u>) und mit Doppelpunkt. Keine Fettschrift.
   
### FORMATVORGABEN:
**Sachverhalt & Anträge**
[Text]

**Streitig**
[Text]

**Entscheidung**
[Text auf Deutsch: Beginne direkt mit der materiellen Würdigung]
"""

    try:
        clean_text = " ".join(urteil_text.split()[:5000])
        response = client.messages.create(
            model="claude-4-6",
            max_tokens=3500,
            temperature=0,
            system="Du bist ein IT-System. Antworte AUSSCHLIESSLICH im JSON-Format.",
            messages=[
                {"role": "user", "content": f"Schritt 1: Übersetze '{vorschau_raw}' ins Deutsche. Schritt 2: Zusammenfassung.\n\nJSON: {{\"vorschau_de\": \"...\", \"zusammenfassung\": \"...\"}}\n\nUrteil:\n{clean_text}\n\n{PROMPT_ZUSAMMENFASSUNG}"}
            ]
        )
        res_data = json.loads(re.search(r'(\{.*\})', response.content[0].text, re.DOTALL).group(1))
        return res_data.get("vorschau_de", vorschau_raw), res_data.get("zusammenfassung", "")
    except Exception as e:
        return vorschau_raw, f"Zusammenfassung aktuell nicht möglich: {str(e)}"

def scrape_bger():
    print(f"--- Scan gestartet für: {ZIEL_DATUM} ---")
    api_key = os.getenv("ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=api_key)
    domain, headers = "https://www.bger.ch", {'User-Agent': 'Mozilla/5.0'}
    
    if not os.path.exists('urteile.json'):
        with open('urteile.json', 'w', encoding='utf-8') as f: json.dump([], f)
    with open('urteile.json', 'r', encoding='utf-8') as f:
        try: archiv_daten = json.load(f)
        except: archiv_daten = []

    tages_ergebnisse = []
    iv_gefunden = False
    ak_gefunden = False

    try:
        base_res = requests.get(f"{domain}/ext/eurospider/live/de/php/aza/http/index_aza.php?lang=de&mode=index", headers=headers)
        soup = BeautifulSoup(base_res.text, 'html.parser')
        tag_link = next((a['href'] for a in soup.find_all('a', href=True) if a.get_text().strip() == ZIEL_DATUM), None)
        
        if tag_link:
            full_tag_url = tag_link if tag_link.startswith("http") else domain + tag_link
            rows = BeautifulSoup(requests.get(full_tag_url, headers=headers).text, 'html.parser').find_all('tr')
            
            # STRENGER FILTER: Nur diese Begriffe im Sachgebiet lösen aus
            iv_keywords = ["invalidenversicherung", "assurance-invalidité", "invalidità", "assurance-invalidité"]
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
                # Nur 9C und 8C Abteilungen
                if not (raw_az.startswith("9C_") or raw_az.startswith("8C_")): continue
                
                # Das Sachgebiet steht immer in der darauffolgenden Zeile (Vorschau)
                vorschau_raw = rows[i+1].get_text().strip() if i+1 < len(rows) else ""
                sachgebiet_text = vorschau_raw.lower()
                
                # Prüfung NUR im Sachgebiet
                ist_iv = any(k in sachgebiet_text for k in iv_keywords)
                ist_ak = any(k in sachgebiet_text for k in ak_keywords)

                if ist_iv or ist_ak:
                    clean_az = raw_az.replace("*", "").strip()
                    kat = "iv" if ist_iv else "ak"
                    if ist_iv and ist_ak: kat = "beide"
                    
                    if ist_iv: iv_gefunden = True
                    if ist_ak: ak_gefunden = True

                    case_url = link_tag['href'] if link_tag['href'].startswith("http") else domain + link_tag['href']
                    case_html = BeautifulSoup(requests.get(case_url, headers=headers).text, 'html.parser').get_text()
                    
                    # Zürich-Rollen-Check
                    iv_zh_fuehrer, iv_zh_gegner = False, False
                    if "IV-Stelle des Kantons Zürich" in case_html[:3000]:
                        start = case_html.find("IV-Stelle des Kantons Zürich")
                        if "Beschwerdeführerin" in case_html[start:start+250]: iv_zh_fuehrer = True
                        else: iv_zh_gegner = True

                    v_text, z_text = summarize_and_translate(case_html, vorschau_raw, client)
                    tages_ergebnisse.append({
                        "aktenzeichen": clean_az, "datum": ZIEL_DATUM, "kategorie": kat,
                        "publikation": "*" in raw_az, "iv_zh_fuehrer": iv_zh_fuehrer, "iv_zh_gegner": iv_zh_gegner,
                        "vorschau": v_text, "zusammenfassung": z_text, "url": case_url
                    })

        # --- DOPPELTE SKIP-LOGIK ---
        if not iv_gefunden:
            tages_ergebnisse.append({
                "aktenzeichen": "INFO_SKIP_IV", "datum": ZIEL_DATUM, "kategorie": "iv",
                "vorschau": "Heute sind keine IV-relevanten Urteile erschienen.",
                "zusammenfassung": "", "url": "", "publikation": False, "iv_zh_fuehrer": False, "iv_zh_gegner": False
            })
        
        if not ak_gefunden:
            tages_ergebnisse.append({
                "aktenzeichen": "INFO_SKIP_AK", "datum": ZIEL_DATUM, "kategorie": "ak",
                "vorschau": "Heute sind keine AK-relevanten Urteile erschienen.",
                "zusammenfassung": "", "url": "", "publikation": False, "iv_zh_fuehrer": False, "iv_zh_gegner": False
            })

        # Speichern
        archiv_daten = [d for d in archiv_daten if d['datum'] != ZIEL_DATUM]
        archiv_daten.extend(tages_ergebnisse)
        archiv_daten.sort(key=lambda x: datetime.strptime(x['datum'], "%d.%m.%Y"), reverse=True)
        with open('urteile.json', 'w', encoding='utf-8') as f:
            json.dump(archiv_daten, f, ensure_ascii=False, indent=4)
        print(f"Scan für {ZIEL_DATUM} abgeschlossen.")
    except Exception as e: print(f"Fehler: {e}")

if __name__ == "__main__":
    scrape_bger()
