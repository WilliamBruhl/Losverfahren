# Test-Datensätze

Drei synthetische Datensätze zum Ausprobieren der Anwendung mit
unterschiedlichen Schemata, Sprachen und Grössen.

| Ordner | Sprache | Merkmale | Pool / Panel | Besonderheit |
|---|---|---|---|---|
| [`wallonia-fr/`](wallonia-fr/) | Französisch | 5 (Genre, Âge, Province, Diplôme, Langue) | 150 / 24 | Realistische wallonische Bevölkerung inkl. Joint Genre×Province |
| [`uk-climate-en/`](uk-climate-en/) | Englisch | 6 (inkl. EthnicGroup, ClimateConcern) | 200 / 30 | Alias-Header `Feature/Value/Count`, optionale Joint-Verteilung Gender×Region |
| [`town-council-de/`](town-council-de/) | Deutsch | 3 (Geschlecht, Alter, Ortsteil) | 20 / 8 | Sehr klein, alle Spalten als deutsche Synonyme (`Nummer`, `Merkmal`, `Wert`, `Anzahl`, `Bemerkung`) |

Alle drei laufen mit `losverfahren.cli draw` (Reproduzier-Aufrufe stehen
im jeweiligen README) und sind als ein-Klick-Demo auch in der Streamlit-
App verwendbar — einfach Pfad in den Datei-Auswahl-Dialog kopieren.

> **Hinweis:** Alle Zahlen sind synthetisch und nur für Tests gedacht.
> Für reale Anwendungen müssen die Marginalen aus offiziellen Statistiken
> stammen (IWEPS/Statbel, ONS, BFS …).
