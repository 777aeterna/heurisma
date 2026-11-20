# Reproducibility Guide (`examples/showcase-hybrid-work/appendix/`)

Run in order from `examples/showcase-hybrid-work/` (not with `python3 -I`):

```bash
python3 -B ../../skills/heurisma/scripts/local_data.py inventory data/
python3 -B appendix/analysis.py --charts-out charts.json --numbers-out appendix/numbers.json > appendix/output.txt
python3 -B ../../skills/heurisma/scripts/render_report.py report.md --out report.html --charts charts.json --appendix appendix/
python3 -B ../../skills/heurisma/scripts/validate_report.py report.md --level 2 --html report.html --strict
```

`analysis.py` enumerates every treatment assignment (70 per subgroup, 4,900 stratified), so its output is deterministic. `appendix/data_attempts.csv` records which sources could and could not be read. Re-render after any edit: the HTML embeds a hash of its sources.
