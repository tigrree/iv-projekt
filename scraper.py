import os
import json
import re
import requests
import urllib3
from datetime import datetime
from bs4 import BeautifulSoup
import anthropic

# Unterdrückt die Warnungen, da wir SSL ignorieren
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# AUTOMATISIERUNG: Aktuelles Datum (für den Live-Betrieb)
ZIEL_DATUM = datetime.now().strftime("%d.%m.%Y")

def summarize_and_translate(urteil_text, vorschau_raw, client):
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

### ZWINGENDES GLOSSAR FÜR ÜBERSETZUNGEN (FR/IT -> DE):
Wenn du französische oder italienische Urteile zusammenfasst, musst du zwingend folgende deutsche Fachbegriffe verwenden:
- "ESS" (Enquête suisse sur la structure des salaires) -> "LSE" (Lohnstrukturerhebung)
- "branche" -> "Branche" (niemals "Branchenlinie")
- "expertise pluridisciplinaire" / "évaluation pluridisciplinaire" -> "interdisziplinäres Gutachten" oder "interdisziplinäre Begutachtung" (niemals "pluridisziplinär")
- "réformer" / "réforme" -> "abändern" / "Abänderung" (niemals "reformieren" oder "Reformation")

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
        clean_text = urteil_text
        response = client.messages.create(
            model="claude-opus-5",
            max_tokens=4000,
            system="Du bist ein IT-System. Antworte AUSSCHLIESSLICH mit den folgenden zwei XML-Tags:\n<vorschau_de>Übersetzung hier</vorschau_de>\n<zusammenfassung>Zusammenfassung hier</zusammenfassung>\n\nVerwende KEIN JSON und erfinde keine anderen Formate.",
            messages=[{"role": "user", "content": f"Schritt 1: Übersetze '{vorschau_raw}' EXAKT ins Deutsche. Schreibe NUR das Sachgebiet in den Tag <vorschau_de>.\nSchritt 2: Fasse das Urteil zusammen und schreibe den Text in den Tag <zusammenfassung>.\n\nUrteil:\n{clean_text}\n\n{PROMPT_ZUSAMMENFASSUNG}"}]
        )
        
        raw_content = ""
        for block in response.content:
            if block.type == "text":
                raw_content = block.text
                break
                
        if not raw_content:
            return vorschau_raw, "Fehler: Die KI hat keinen auslesbaren Text-Block zurückgegeben."
        
        # --- ROBUSTES XML-PARSING (Fehlerbehebung) ---
        v_match = re.search(r'<vorschau_de>(.*?)</vorschau_de>', raw_content, re.DOTALL | re.IGNORECASE)
        z_match = re.search(r'<zusammenfassung>(.*?)</zusammenfassung>', raw_content, re.DOTALL | re.IGNORECASE)
        
        v_de = ""
        z_de = ""

        # Vorschau parsen
        if v_match:
            v_de = v_match.group(1).strip()
        elif re.search(r'<vorschau_de>', raw_content, re.IGNORECASE):
            # Fallback falls schliessender Tag fehlt oder fehlerhaft ist
            v_de = re.split(r'(?i)<vorschau_de>', raw_content)[1].split('<')[0].strip()

        # Zusammenfassung parsen
        if z_match:
            z_de = z_match.group(1).strip()
        elif re.search(r'<zusammenfassung>', raw_content, re.IGNORECASE):
            # Fallback falls schliessender Tag fehlt (z.B. wegen Text-Länge abgeschnitten)
            z_de = re.split(r'(?i)<zusammenfassung>', raw_content)[1].strip()
            # Entfernt eventuelle Markdown-Fragmente am Ende, falls vorhanden
            z_de = re.sub(r'
