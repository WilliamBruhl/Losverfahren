# Kleiner Bürgerrat einer fiktiven Gemeinde

Mini-Datensatz zum Testen von Randfällen:

* nur **20 Kandidaten**, Panelgrösse 8, ohne Ersatzliste,
* nur 3 Merkmale (Geschlecht, Alter, Ortsteil),
* CSV-Spalten verwenden bewusst **deutsche Synonyme** (`Nummer`,
  `Merkmal`, `Wert`, `Anzahl`, `Bemerkung`) — beim Einlesen erscheint
  pro Spalte eine Info-Zeile mit der erkannten Übersetzung.

## Reproduzieren

```bash
python -m losverfahren.cli draw \
  --candidates 03-gui-tool/test-data/town-council-de/candidates.csv \
  --population 03-gui-tool/test-data/town-council-de/population.csv \
  --panel-size 8 --substitutes 0 --seed 42 \
  --output /tmp/town.xlsx
```
