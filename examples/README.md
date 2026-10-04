# Examples

Place `Flat_Summary.csv` (or any multi-segment performance extract) here:

```bash
stride-x scan examples/Flat_Summary.csv --csv-out findings.csv
```

Required minimum columns (names auto-detected when possible):

- A date column
- A profit / PnL column
- A stake / GMV / turnover column
- One or more segment columns (Market, Platform, …)
