import requests
from bs4 import BeautifulSoup
import json
import os
import time
import re
from datetime import datetime
import anthropic

# AUTOMATISIERUNG: Aktuelles Datum
ZIEL_DATUM = "20.03.2026"

def translate_preview(text):
    # Einfache Übersetzung der Vorschau via Groq (dafür reicht Llama völlig aus)
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key or not text: return text
    german_indicators = ["invalidenversicherung", "rente", "iv-stelle", "versicherungsgericht"]
    if any(word in text.lower() for word in german_indicators): return text
    
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "system", "content": "Du bist ein Übersetzer."}, {"role": "user", "content": f"Übersetze kurz ins Deutsche: {text}"}],
        "temperature": 0.1
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=20)
        return response.json()['choices'][0]['message']['content'].strip().replace('"', '')
    except: return text

def summarize_with_ai(urteil_text):
    # SCHALTER: True = Claude (Anthropic), False = Groq (Llama)
    USE_CLAUDE = True 
    
    # Gemeinsamer Prompt für beide Modelle    
    PROMPT_TEXT = """Du bist ein erfahrener Schweizer Jurist und Bundesrichter mit Schwerpunkt Sozialversicherungsrecht. Deine Aufgabe ist es, den nachfolgenden Bundesgerichtsentscheid präzise zusammenzufassen.

### VORAB-INFORMATION ZUM URTEILSAUFBAU:
Ein Bundesgerichtsurteil folgt einer strikten Struktur, die du bei der Analyse beachten musst (das Rubrum und das Dispositiv sind nicht relevant):
- Sachverhalt: Enthält den materiellen Sachverhalt, die medizinische Historie, die Prozessgeschichte und die Anträge. Achtung: Dies sind noch NICHT die Erwägungen des Bundesgerichts.
- Erwägungen (Ziffern 1, 2, 3...): Hier findet die eigentliche rechtliche Prüfung statt.

### SCHRITTWEISE ANALYSE-STRATEGIE (LOGISCHE PRIORITÄT):
Gehe strikt in dieser Reihenfolge vor:
SCHRITT 1 SPRACHE: Analysiere das Urteil (DE, FR oder IT) und erstelle die Zusammenfassung VOLLSTÄNDIG auf DEUTSCH.
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
4. Zum Entscheid:
4.1 Medizinische Aspekte: Fokus auf Gutachten und RAD-Stellungnahmen. Sofern das oder die Gutachten und/oder die RAD-Stellungnahme oder RAD-Stellungnahmen nicht thematisiert wird/werden, musst du keine Ausführungen dazu erfassen.
4.2 Übergangsrecht: Falls WEIV (altes vs. neues Recht ab 1.1.2022) thematisiert wird, kurz erwähnen, welches Recht anwendbar ist. Sofern das WEIV nicht thematisiert wird, musst du keine Ausführungen zum WEIV erfassen.

### STRIKTE INHALTSFILTER:
1. KEINE Erwähnung, dass die Vorinstanz die Bestimmungen zu den Begriffen der Invalidität und der Erwerbsunfähigkeit richtig dargelegt hat. Das ist für die Zusammenfassung wertlos.
2. KEINE Einleitung ("In diesem Urteil geht es um...").
3. KEINE Standard-Sätze zu Art. 95, 97, 105, 106 BGG. Das ist für die Zusammenfassung wertlos, es sei denn, das Bundesgericht wendet diese Artikel im Einzelfall spezifisch auf eine Rüge an.
4. KEINE Sätze wie "Die Vorinstanz hat die Bestimmungen richtig dargelegt".
5. KEINE redundanten Aufzählungen ("Das Gericht hat zu prüfen...").
6. Rubrum und Dispositiv (als Textblock) weglassen.
7. Prozesskosten/Entschädigungen weglassen.
8. Behörden: Stellungnahmen des BSV nur erwähnen, wenn diese tatsächlich vorhanden sind. Erwähne das BSV nicht, sofern es auf eine Stellungnahme verzichtet hat.
9. VERBOT DER SYNTHESE: Erstelle keine eigenen logischen Verknüpfungen zwischen Parteivorbringen und dem Urteil. Wenn das Bundesgericht eine Rüge nur wiedergibt, ohne sie sich zu eigen zu machen, darf sie nicht als Feststellung des Gerichts erscheinen. Die Zusammenfassung muss ein neutrales Referat des Textes sein, keine rechtliche Würdigung durch die KI.

### STRIKTE FORMREGELN:
1. Anonymisierung:
1.1. Namen von Personen (z. B. B.________) konsequent auf den Buchstaben und den Punkt reduzieren (Beispiel: B. B.).
1.2. Gutachterstellen: Nur die Abkürzung angeben (z.B. ZMB statt Zentrum für Medizinische Begutachtung).
2. Schreibstil: Konsequent 'ss' statt 'ß'.
3. Zitatpflicht: Jede inhaltliche Feststellung MUSS mit der Erwägung (z.B. E. 7.1) belegt werden.
4. Indirekte Rede & Quelle: Nutze bei der Wiedergabe von Parteivorbringen konsequent Verben wie „macht geltend“, „behauptet“ oder „rügt“. Bei der Vorinstanz „ging davon aus“ oder „erwog“. Nur beim Bundesgericht verwendest du Feststellungen wie „stellt fest“ oder „erkennt“.
5. Wahrheitsgehalt: Wenn du eine Kritik (z.B. „medizinische Fragen selbst interpretiert“) erwähnst, stelle klar, ob dies eine Rüge des Beschwerdeführers ist oder eine Feststellung des Bundesgerichts.
6. Zwingende Übersetzung: Falls das Urteil auf Französisch oder Italienisch verfasst ist, müssen ALLE Fachbegriffe (z.B. „perizia“, „capacità lavorativa“, „istanza precedente“) zwingend durch ihre korrekten deutschen Entsprechungen (z.B. „Gutachten“, „Arbeitsfähigkeit“, „Vorinstanz“) ersetzt werden.

### FORMATVORGABEN:
**Sachverhalt & Anträge**
[Text]

**Streitig**
[Text]

**Entscheidung**
[Text auf Deutsch: Beginne direkt mit der materiellen Würdigung (dort wo die eigentliche Begründung des Bundesgerichts zum Streitpunkt einsetzt)]

Antworte NUR in Deutsch. Keine Einleitung.
Hier ist das Urteil:
"""
    
if USE_CLAUDE:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key: return "Claude API Key fehlt."
        try:
            client = anthropic.Anthropic(api_key=api_key)
            # Claude verträgt bis zu 4000 Wörter problemlos
            clean_text = " ".join(urteil_text.split()[:4000])
            message = client.messages.create(
                model="claude-3-5-sonnet-20240620",
                max_tokens=2000,
                temperature=0,
                system="Du bist ein präziser Schweizer Bundesrichter. Antworte NUR auf Deutsch. Nutze 'ss'. Übersetze alle Fachbegriffe korrekt.",
                messages=[{"role": "user", "content": PROMPT_TEXT + "\n\nUrteil:\n" + clean_text}]
            )
            antwort = message.content[0].text.strip()
        except Exception as e:
            return f"Fehler bei Claude: {e}"
    else:
        # BACKUP: Groq Logik
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key: return "Groq API Key fehlt."
        clean_text = " ".join(urteil_text.split()[:1500])
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": "Du bist ein präziser Schweizer Bundesrichter. Antworte NUR auf Deutsch. Nutze 'ss'."},
                {"role": "user", "content": PROMPT_TEXT + "\n\nUrteil:\n" + clean_text}
            ],
            "temperature": 0.0
        }
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=120)
            antwort = response.json()['choices'][0]['message']['content'].strip()
        except Exception as e:
            return f"Fehler bei Groq: {e}"

    # Säuberung von Unterstrichen (für beide Modelle)
    antwort = re.sub(r'([A-Z]\.)_+', r'\1', antwort)
    antwort = re.sub(r'([A-Z]\s[A-Z]\.)_+', r'\1', antwort)
    return antwort

def scrape_bger():
    print(f"--- Scan gestartet für: {ZIEL_DATUM} ---")
    domain = "https://www.bger.ch"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    if not os.path.exists('urteile.json'):
        with open('urteile.json', 'w', encoding='utf-8') as f: json.dump([], f)
    
    with open('urteile.json', 'r', encoding='utf-8') as f:
        try: archiv_daten = json.load(f)
        except: archiv_daten = []

    try:
        base_res = requests.get(f"{domain}/ext/eurospider/live/de/php/aza/http/index_aza.php?lang=de&mode=index", headers=headers)
        soup = BeautifulSoup(base_res.text, 'html.parser')
        tag_link = next((a['href'] for a in soup.find_all('a', href=True) if a.get_text().strip() == ZIEL_DATUM), None)
        
        if not tag_link: 
            print(f"Datum {ZIEL_DATUM} noch nicht gelistet.")
            return

        full_tag_url = tag_link if tag_link.startswith("http") else domain + tag_link
        day_soup = BeautifulSoup(requests.get(full_tag_url, headers=headers).text, 'html.parser')
        
        tages_ergebnisse = []
        rows = day_soup.find_all('tr')
        
        for i in range(len(rows)):
            row = rows[i]
            link_tag = row.find('a', href=True)
            if not link_tag: continue
            raw_az = link_tag.get_text().strip()
            if not (raw_az.startswith("9C_") or raw_az.startswith("8C_")): continue
            
            clean_az = raw_az.replace("*", "").strip()
            is_publikation = "*" in raw_az
            vorschau_text = rows[i+1].get_text().strip() if i + 1 < len(rows) else ""

            if any(key in (row.get_text() + vorschau_text).lower() for key in ["invalid"]):
                print(f"Treffer: {clean_az}")
                case_url = link_tag['href'] if link_tag['href'].startswith("http") else domain + link_tag['href']
                case_html = BeautifulSoup(requests.get(case_url, headers=headers).text, 'html.parser').get_text()
                
                # Rollenprüfung
                iv_zh_fuehrer, iv_zh_gegner = False, False
                search_text = " ".join(case_html.split("Sachverhalt:")[0].split())
                if "IV-Stelle des Kantons Zürich" in search_text:
                    if "Beschwerdeführerin" in search_text: iv_zh_fuehrer = True
                    elif "Beschwerdegegnerin" in search_text: iv_zh_gegner = True

                existing = next((d for d in archiv_daten if d['aktenzeichen'] == clean_az), None)
                if existing and "nicht verfügbar" not in existing['zusammenfassung']:
                    zusammenfassung = existing['zusammenfassung']
                else:
                    zusammenfassung = summarize_with_ai(case_html)
                    time.sleep(2) 

                tages_ergebnisse.append({
                    "aktenzeichen": clean_az, "datum": ZIEL_DATUM, "publikation": is_publikation,
                    "iv_zh_fuehrer": iv_zh_fuehrer, "iv_zh_gegner": iv_zh_gegner,
                    "vorschau": translate_preview(vorschau_text), "zusammenfassung": zusammenfassung, "url": case_url
                })

        if tages_ergebnisse:
            archiv_daten = [d for d in archiv_daten if d['datum'] != ZIEL_DATUM]
            archiv_daten.extend(tages_ergebnisse)
            archiv_daten.sort(key=lambda x: datetime.strptime(x['datum'], "%d.%m.%Y"), reverse=True)
            with open('urteile.json', 'w', encoding='utf-8') as f:
                json.dump(archiv_daten, f, ensure_ascii=False, indent=4)
        print(f"Scan für {ZIEL_DATUM} abgeschlossen.")
    except Exception as e:
        print(f"Fehler: {e}")

if __name__ == "__main__":
    scrape_bger()
