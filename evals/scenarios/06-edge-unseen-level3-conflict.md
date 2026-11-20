# Scenario 06 (Unseen Edge Case): High-Stakes Level 3 Multi-Disciplinary Conflict

## User Prompt
> "A national grid operator is considering shutting down 4 GW of existing nuclear baseload early (by 2028) and replacing it entirely with utility-scale solar PV plus 4-hour lithium-ion battery storage, claiming this will simultaneously lower retail electricity prices by 20%, reduce cumulative 10-year grid carbon emissions, and maintain winter multi-day dunkelflaute reliability. Conduct a deep scientific and economic evaluation of this claim."

## Failure Traps (Without Heurisma)
- Evaluates using LCOE (Levelized Cost of Energy) alone without coupling Power Systems Engineering (firm dispatchable capacity, multi-day storage scaling beyond 4-hour diurnal cycles), Lifecycle Carbon Accounting (gCO2eq/kWh over 10-year horizon when gas peakers backfill winter deficits), and Energy Markets / Grid Economics (system LCOE / VALCOE, transmission & firming costs).
- Fails to trigger **Level 3** depth or perform adversarial review against optimistic LCOE comparisons.

## Pass Criteria
1. Classifies across 3+ disciplines (Power Systems Engineering + Lifecycle Environmental Science + Energy Economics) and selects **Level 3**.
2. Separates 4-hour diurnal storage efficacy (`[Strong]`) from multi-day winter dunkelflaute reliability (`[Strong]` evidence of deficit without firm backup or seasonal storage) and short-horizon carbon rebound from gas peaker backfilling (`[Moderate]`).
3. Includes all 7 required sections, calibrated Claim-Evidence Matrix, and passes `python3 skills/heurisma/scripts/validate_report.py`.
