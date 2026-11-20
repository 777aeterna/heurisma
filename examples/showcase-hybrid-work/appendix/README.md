# Reproducibility Guide (`examples/showcase-hybrid-work/appendix/`)

Run in order from `examples/showcase-hybrid-work/`:

```bash
python3 -B ../../skills/heurisma/scripts/local_data.py inventory data/
python3 -B appendix/analysis.py --charts-out charts.json --numbers-out appendix/numbers.json > appendix/output.txt
python3 -B ../../skills/heurisma/scripts/render_report.py report.md --out report.html --charts charts.json --appendix appendix/
python3 -B ../../skills/heurisma/scripts/validate_report.py report.md --level 2 --html report.html --strict
```
