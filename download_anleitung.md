=== PRODUKT-ABHOLUNG ===

Kunde: Nach Zahlung (ETH an Wallet) und Aufgabenverarbeitung (inbox -> outbox) erhält der Kunde das Produkt.

Abholung:
1. Kunde zahlt ETH an Wallet (QR-Code: wallet/wallet_qr.png)
2. Firma verarbeitet Aufgabe (Agent tick)
3. Produkt erscheint in outbox/ (z.B. bezahlt_auftrag_001.txt.processed)
4. Kunde erhält Datei per Download oder Zugriff auf outbox/

Beispiel:
- Auftrag: inbox/bezahlt_auftrag_001.txt
- Produkt: outbox/bezahlt_auftrag_001.txt.processed

Für automatisierten Download: Kunde kann die .processed-Datei direkt aus dem Projektverzeichnis abrufen (lokaler Zugriff oder über einen einfachen HTTP-Server).
