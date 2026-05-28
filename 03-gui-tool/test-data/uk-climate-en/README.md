# UK national climate assembly — synthetic test dataset

Six-feature example loosely inspired by the demographic targets of
*Climate Assembly UK* (2020) but at smaller scale. All numbers are
**synthetic**; consult ONS / Census 2021 for real figures.

* Headers in English.
* `population.csv` uses the alias column names `Feature, Value, Count` —
  the tool will auto-recognise them and emit one info-line per alias.
* 6 stratification dimensions (Gender, AgeGroup, Region, Education,
  EthnicGroup, ClimateConcern).
* Optional joint Gender × Region table (`population_joint.csv`) also
  uses alias headers `Gender, Region, Count`.

## Reproduce

```bash
python -m losverfahren.cli draw \
  --candidates 03-gui-tool/test-data/uk-climate-en/candidates.csv \
  --population 03-gui-tool/test-data/uk-climate-en/population.csv \
  --joint      03-gui-tool/test-data/uk-climate-en/population_joint.csv \
  --panel-size 30 --substitutes 10 --seed 2020 \
  --output /tmp/uk.xlsx
```
