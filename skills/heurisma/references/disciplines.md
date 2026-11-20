# Scientific Discipline Taxonomy & Evidence Standards

Part of **Heurisma** (loaded during **Stage 0: Cognitive Triage**). Use this reference to classify the user's inquiry into one or more scientific branches, select the domain-appropriate evidence hierarchy, and avoid methodological traps.

---

## 1. Discipline Classification Matrix

| Scientific Branch | Sub-Domains | Gold-Standard Evidence (Tier 1) | Secondary / Supporting (Tier 2) | Low-Tier / Never Treat as Proof (Tier 3) | Signature Methodological Traps |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **1. Formal Sciences** | Mathematics, Symbolic Logic, Theoretical Computer Science, Game Theory, Cryptography | Deductive formal proofs, constructive algorithms, verified counterexamples, tight asymptotic bounds | Peer-reviewed mechanized/assisted proofs, empirical verification across finite bounds | Heuristic intuition, " holds for first $N$ examples", analogies, web opinions | Mistaking empirical pattern matching for universal proof; omitting edge/degenerate cases ($n=0, 1$, non-commutative, pathological topologies) |
| **2. Natural & Physical Sciences** | Physics, Chemistry, Biology, Earth & Marine Sciences, Ecology, Materials Science | Replicated field & laboratory experiments under realistic boundary conditions, conservation laws, dimensional analysis | Validated numerical simulations, single peer-reviewed experimental studies, standard lab assays (e.g., ASTM/ISO) | Unreplicated preprints, idealized lab tests extrapolated blindly to harsh field environments, vendor brochures | **Lab-to-Nature Extrapolation:** assuming $30^\circ\text{C}$ aerobic lab kinetics hold in $<10^\circ\text{C}$ or anoxic real environments; ignoring mass/energy conservation |
| **3. Biomedical & Health Sciences** | Clinical Medicine, Epidemiology, Nutrition, Pharmacology, Public Health | Systematic reviews & meta-analyses of randomized controlled trials (RCTs), pre-registered double-blind human RCTs with hard clinical endpoints | Prospective cohort studies, small/short-term human RCTs with surrogate biomarkers, Mendelian randomization | Animal/rodent studies extrapolated to human lifespan, unadjusted cross-sectional surveys, case reports, wellness blogs | Confounding calorie restriction with meal timing; treating rodent longevity or *in vitro* mechanisms as clinical human proof; ignoring dropout/adherence bias |
| **4. Social Sciences & Economics** | Microeconomics, Macroeconomics, Behavioral Economics, Sociology, Political Science, Public Policy | Field RCTs, natural experiments with credible causal identification (Difference-in-Differences, Instrumental Variables, Regression Discontinuity) | Longitudinal panel studies with fixed effects, audited municipal/institutional administrative datasets | Uncontrolled before/after anecdotes, theoretical price-elasticity models without structural constraints, opinion polls | Confusing correlation with causation; survivorship/selection bias; ignoring incidence (who bears a tax/fee vs. who remits it) and behavioral substitution |
| **5. Engineering & Applied Sciences** | Manufacturing, Electrical/Mechanical/Chemical Engineering, Systems & Software Engineering, Energy Systems | Audited production yields, multi-cycle pack/system benchmarks under realistic load, reproducible benchmark suites | Pilot-line B-sample demonstrations, single-cell/component lab tests, teardown cost models | OEM press-release roadmap dates, single-layer coin-cell records cited as commercial pack specs, vendor whitepapers | **Coin-Cell-to-Gigafactory Fallacy:** equating laboratory prototype density with mass-manufacturing yield, stack-pressure mass penalty, and $/kWh cost parity |
| **6. Humanities & Historical Inquiry** | History, Philosophy, Legal Studies, Historiography, Science & Technology Studies (STS) | Authenticated primary documents, contemporaneous archival records, direct statutory/case-law text | Peer-reviewed monographs cross-checking multiple independent archives, archaeological consensus | Tertiary summaries, anachronistic modern projections, single partisan chronicles cited uncritically | Treating secondary commentary as primary evidence; ignoring provenance, translation drift, or survivorship bias in historical archives |

---

## 2. Interdisciplinary Bridge Protocol

Most high-value real-world research prompts cross **2 or more branches** (e.g., a municipal bioplastic policy crosses *Marine Polymer Chemistry* + *Behavioral Economics* + *Supply-Chain Engineering*; an EV battery forecast crosses *Electrochemistry* + *Manufacturing Engineering* + *Industrial Economics*).

When 2+ branches apply, you MUST follow this 3-step Bridge Protocol in **Stage 0** and **Section 2 / Section 3** of the report:

1. **Name Every Active Branch Explicitly:** List each discipline and the specific sub-question it governs.
2. **Enforce Domain-Specific Evidence Standards:** Do not evaluate an economic viability claim using chemistry lab papers, and do not evaluate a physical degradation or electrochemistry barrier using market-analyst CAGR forecasts.
3. **Identify Cross-Domain Coupling & Bottlenecks:** State where one discipline's constraint invalidates another's assumption.
   - *Example A (Bioplastics):* Even if behavioral economics shows a $0.35 fee shifts vendor demand, industrial supply-chain capacity (~70k MT global PHA) and polymer processing windows limit 36-month substitution, while PLA/PBAT blending to lower cost breaks marine biodegradability.
   - *Example B (Solid-State Batteries):* Even if sulfide electrolytes achieve high ionic conductivity in electrochemistry, mechanical stack-pressure fixtures erode pack-level Wh/kg in mechanical engineering, while LFP price deflation (<$85/kWh) shifts the economic parity threshold in industrial economics.
