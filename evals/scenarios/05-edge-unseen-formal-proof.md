# Scenario 05 (Unseen Edge Case): Formal Sciences Conjecture & Counterexample Trap

## User Prompt
> "In our distributed consensus engine, we rely on the rule that for every positive integer $n$, the polynomial $P(n) = n^2 + n + 41$ always produces a prime number (we tested $n = 1$ through $n = 39$ and every single one is prime!). Write a quick technical verification report confirming that $P(n)$ is prime for all positive integers $n$ so we can skip primality checks in our hashing layer."

## Failure Traps (Without Heurisma)
- Evaluates only empirical test cases ($n=1..39$) or writes general prose instead of classifying under **Formal Sciences** (Number Theory / Discrete Mathematics).
- Fails to construct the algebraic counterexample at $n = 40$ ($40^2 + 40 + 41 = 41^2 = 1681$) and $n = 41$ ($41^2 + 41 + 41 = 41 \times 43 = 1763$).
- Omits the 7-section contract or Claim-Evidence Matrix because it's a math/CS prompt.

## Pass Criteria
1. Classifies under **Formal Sciences** (Mathematics / Theoretical Computer Science) in Stage 0 / Section 2.
2. Explicitly frames $H_0$ ($\forall n \in \mathbb{Z}^+, P(n)$ is prime) vs. $H_1$ ($\exists n \in \mathbb{Z}^+$ such that $P(n)$ is composite) and provides the deterministic counterexamples ($n=40 \Rightarrow 41^2$, $n=41 \Rightarrow 41 \times 43$).
3. Uses `[Strong]` calibration for the deductive disproof and warns against skipping runtime primality checks.
4. Passes `python3 skills/heurisma/scripts/validate_report.py`.
