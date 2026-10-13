=== KUNDE LEGT AUFTRAG IN INBOX ===

Manuell:
1. Kunde erstellt Textdatei (z. B. "mein_auftrag.txt")
2. Kunde kopiert Datei nach: C:\Users\frank\Desktop\ghdfh\autonom-automatum\inbox\

Automatisch (Kunde nutzt Skript):
# Windows (PowerShell)
echo "AUFGABE: KI-Produkt-Entwicklung" > inbox\mein_neuer_auftrag.txt

# Python
with open('C:\\Users\\frank\\Desktop\\ghdfh\\autonom-automatum\\inbox\\mein_neuer_auftrag.txt', 'w') as f:
    f.write('AUFGABE: KI-Produkt-Entwicklung\\nBeschreibung: Automatisierte Optimierung.')

Der Agent (`agent.tick()`) erkennt die Datei automatisch und verarbeitet sie als DB-Task.
