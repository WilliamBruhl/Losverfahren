# Assemblée citoyenne wallonne — jeu de données synthétique

Inspiré par les méthodes utilisées pour le *Dialogue citoyen permanent* de
la Région wallonne et de la Communauté germanophone (Bürgerdialog Ostbelgien).

* `candidates.csv` — 150 personnes tirées au hasard parmi les répondants
  fictifs ; en-têtes en français (`Genre`, `Âge`, `Province`, `Diplôme`,
  `Langue`).
* `population.csv` — marginales pour les 5 mêmes attributs, basées sur des
  estimations approximatives de la population adulte wallonne (~2,9 M
  d'habitants de 18 ans et plus, 2024). En-têtes francisés (`Merkmal` →
  `feature`, `Anzahl` → `count`, etc. ne sont **pas** utilisés ici ; on
  prend les noms français standards `feature/value/count/note`).
* `population_joint.csv` — distribution conjointe Genre × Province pour les
  10 cellules principales.

Les chiffres sont **arrondis et synthétiques** ; ils ne remplacent pas les
publications officielles de l'IWEPS / Statbel.

## Reproduire la sélection

```bash
python -m losverfahren.cli draw \
  --candidates 03-gui-tool/test-data/wallonia-fr/candidates.csv \
  --population 03-gui-tool/test-data/wallonia-fr/population.csv \
  --joint      03-gui-tool/test-data/wallonia-fr/population_joint.csv \
  --panel-size 24 --substitutes 12 --seed 1830 \
  --output /tmp/wallonia.xlsx
```
