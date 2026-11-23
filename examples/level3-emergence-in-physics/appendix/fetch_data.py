#!/usr/bin/env python3
"""Stage 2 literature acquisition script for Emergence in Physics (Heurisma v0.10.1).

Queries OpenAlex and arXiv via papers.py, logging all searches and attempts
to appendix/papers.csv, appendix/search_log.csv, appendix/download_log.csv,
and appendix/data_attempts.csv. Respects HEURISMA_OFFLINE=1.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

APPENDIX = Path(__file__).resolve().parent
REPORT_DIR = APPENDIX.parent
SKILL_SCRIPTS = REPORT_DIR.parent / ".agents" / "skills" / "heurisma" / "scripts"
PAPERS_PY = SKILL_SCRIPTS / "papers.py"

SEARCHES = [
    # Foundational condensed matter & symmetry breaking
    ("openalex", "More Is Different broken symmetry Anderson", 5),
    ("openalex", "The Theory of Everything Laughlin Pines", 5),
    ("openalex", "Crystal Statistics Two-Dimensional Model Order-Disorder Transition Onsager", 5),
    ("openalex", "Statistical Theory of Equations of State Phase Transitions Yang Lee", 5),
    ("openalex", "Renormalization group theory basis formulation statistical physics Fisher", 5),
    # Philosophy of physics: weak vs strong emergence & limits
    ("openalex", "Less is Different Emergence and Reduction Reconciled Butterfield", 5),
    ("openalex", "Emergence singularities and symmetry breaking Batterman", 5),
    ("arxiv", "Less is Different Emergence and Reduction Reconciled Butterfield", 3),
    # Formal undecidability & computability barriers
    ("openalex", "Undecidability of the spectral gap Cubitt Perez-Garcia Wolf", 5),
    ("arxiv", "Undecidability of the spectral gap Cubitt", 3),
    ("arxiv", "More really is different Gu Weedbrook", 3),
    # Topological order & emergent gauge fields
    ("openalex", "Choreographed entanglement dances topological states matter Wen", 5),
    ("arxiv", "Emergent gauge fields topological order Wen", 5),
    # Finite-size scaling & Binder cumulant
    ("openalex", "Finite size scaling analysis of Ising model block distribution functions Binder", 5),
    ("openalex", "Collective Monte Carlo Updating for Spin Systems Wolff", 5),
]


def main() -> int:
    for provider, query, limit in SEARCHES:
        cmd = [
            sys.executable,
            "-B",
            str(PAPERS_PY),
            "search",
            "--appendix",
            str(APPENDIX),
            "--provider",
            provider,
            "--query",
            query,
            "--limit",
            str(limit),
        ]
        print(f"\n>>> [{provider}] {query}", flush=True)
        res = subprocess.run(cmd, cwd=str(REPORT_DIR), text=True)
        if res.returncode != 0:
            print(f"    (non-zero exit {res.returncode}; logged in data_attempts.csv)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
