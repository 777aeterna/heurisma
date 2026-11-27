#!/usr/bin/env python3
"""Zero-dependency dimensional analysis (Buckingham Pi) and symbolic law discovery engine (Python >= 3.9, stdlib only)."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import random
import re
import statistics
import sys
from typing import Any, Callable

_SCRIPTS_DIR = str(Path(__file__).resolve().parent)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)
from contracts import (  # noqa: E402
    CONJECTURES_JSON as CONJECTURES_JSON,
    __version__ as __version__,
)

DIMENSIONS: tuple[str, ...] = ("M", "L", "T", "Theta", "I", "N")


class UnitError(ValueError):
    """Raised when a physical unit expression is invalid or dimensionally inconsistent."""


class ConjectureError(ValueError):
    """Raised when symbolic law discovery inputs are degenerate or malformed."""


# Exact exponent vectors over DIMENSIONS = (M, L, T, Theta, I, N)
_UNIT_TABLE: dict[str, tuple[int, int, int, int, int, int]] = {
    "1": (0, 0, 0, 0, 0, 0),
    "dimensionless": (0, 0, 0, 0, 0, 0),
    "none": (0, 0, 0, 0, 0, 0),
    "rad": (0, 0, 0, 0, 0, 0),
    "sr": (0, 0, 0, 0, 0, 0),
    "%": (0, 0, 0, 0, 0, 0),
    "deg": (0, 0, 0, 0, 0, 0),
    # Mass (M)
    "kg": (1, 0, 0, 0, 0, 0),
    "g": (1, 0, 0, 0, 0, 0),
    "mg": (1, 0, 0, 0, 0, 0),
    "t": (1, 0, 0, 0, 0, 0),
    # Length (L)
    "m": (0, 1, 0, 0, 0, 0),
    "cm": (0, 1, 0, 0, 0, 0),
    "mm": (0, 1, 0, 0, 0, 0),
    "um": (0, 1, 0, 0, 0, 0),
    "nm": (0, 1, 0, 0, 0, 0),
    "km": (0, 1, 0, 0, 0, 0),
    "au": (0, 1, 0, 0, 0, 0),
    "pc": (0, 1, 0, 0, 0, 0),
    # Time (T)
    "s": (0, 0, 1, 0, 0, 0),
    "ms": (0, 0, 1, 0, 0, 0),
    "us": (0, 0, 1, 0, 0, 0),
    "ns": (0, 0, 1, 0, 0, 0),
    "min": (0, 0, 1, 0, 0, 0),
    "h": (0, 0, 1, 0, 0, 0),
    "hr": (0, 0, 1, 0, 0, 0),
    "d": (0, 0, 1, 0, 0, 0),
    "day": (0, 0, 1, 0, 0, 0),
    "yr": (0, 0, 1, 0, 0, 0),
    # Temperature (Theta)
    "K": (0, 0, 0, 1, 0, 0),
    # Electric current (I)
    "A": (0, 0, 0, 0, 1, 0),
    "mA": (0, 0, 0, 0, 1, 0),
    # Amount of substance (N)
    "mol": (0, 0, 0, 0, 0, 1),
    "mmol": (0, 0, 0, 0, 0, 1),
    # Derived SI units
    "Hz": (0, 0, -1, 0, 0, 0),
    "kHz": (0, 0, -1, 0, 0, 0),
    "MHz": (0, 0, -1, 0, 0, 0),
    "GHz": (0, 0, -1, 0, 0, 0),
    "N": (1, 1, -2, 0, 0, 0),
    "kN": (1, 1, -2, 0, 0, 0),
    "dyn": (1, 1, -2, 0, 0, 0),
    "J": (1, 2, -2, 0, 0, 0),
    "kJ": (1, 2, -2, 0, 0, 0),
    "MJ": (1, 2, -2, 0, 0, 0),
    "eV": (1, 2, -2, 0, 0, 0),
    "erg": (1, 2, -2, 0, 0, 0),
    "W": (1, 2, -3, 0, 0, 0),
    "kW": (1, 2, -3, 0, 0, 0),
    "MW": (1, 2, -3, 0, 0, 0),
    "GW": (1, 2, -3, 0, 0, 0),
    "Pa": (1, -1, -2, 0, 0, 0),
    "kPa": (1, -1, -2, 0, 0, 0),
    "MPa": (1, -1, -2, 0, 0, 0),
    "GPa": (1, -1, -2, 0, 0, 0),
    "bar": (1, -1, -2, 0, 0, 0),
    "atm": (1, -1, -2, 0, 0, 0),
    "C": (0, 0, 1, 0, 1, 0),
    "V": (1, 2, -3, 0, -1, 0),
    "kV": (1, 2, -3, 0, -1, 0),
    "mV": (1, 2, -3, 0, -1, 0),
    "F": (-1, -2, 4, 0, 2, 0),
    "Ohm": (1, 2, -3, 0, -2, 0),
    "ohm": (1, 2, -3, 0, -2, 0),
    "Wb": (1, 2, -2, 0, -1, 0),
    "T": (1, 0, -2, 0, -1, 0),
    "H": (1, 2, -2, 0, -2, 0),
}

_TOKEN_RE = re.compile(
    r"\s*(?:(\*\*|\^|\*|/|·|\(|\))|([+-]?\d+(?:\.\d+)?)|([A-Za-z%][A-Za-z0-9_]*))"
)


def _tokenize_unit(expr: str) -> list[tuple[str, str]]:
    pos = 0
    tokens: list[tuple[str, str]] = []
    while pos < len(expr):
        if expr[pos].isspace():
            pos += 1
            continue
        m = _TOKEN_RE.match(expr, pos)
        if not m:
            raise UnitError(f"Invalid syntax in unit expression {expr!r} near {expr[pos:]!r}.")
        op, num, ident = m.groups()
        if op is not None:
            tokens.append(("OP", "^" if op == "**" else ("*" if op == "·" else op)))
        elif num is not None:
            tokens.append(("NUM", num))
        elif ident is not None:
            tokens.append(("ID", ident))
        pos = m.end()
    return tokens


class _UnitParser:
    def __init__(self, tokens: list[tuple[str, str]], raw: str) -> None:
        self.tokens = tokens
        self.pos = 0
        self.raw = raw

    def peek(self) -> tuple[str, str] | None:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def consume(self) -> tuple[str, str]:
        tok = self.peek()
        if tok is None:
            raise UnitError(f"Unexpected end of unit expression {self.raw!r}.")
        self.pos += 1
        return tok

    def parse_expr(self) -> tuple[Fraction, ...]:
        vec = self.parse_term()
        while True:
            nxt = self.peek()
            if nxt is None or nxt == ("OP", ")"):
                break
            if nxt == ("OP", "*") or nxt == ("OP", "/"):
                op = self.consume()[1]
                rhs = self.parse_term()
                sign = Fraction(1) if op == "*" else Fraction(-1)
                vec = tuple(a + sign * b for a, b in zip(vec, rhs))
            elif nxt[0] in ("ID", "NUM") or nxt == ("OP", "("):
                rhs = self.parse_term()
                vec = tuple(a + b for a, b in zip(vec, rhs))
            else:
                raise UnitError(f"Unexpected token {nxt[1]!r} in unit expression {self.raw!r}.")
        return vec

    def parse_term(self) -> tuple[Fraction, ...]:
        base = self.parse_factor()
        nxt = self.peek()
        if nxt == ("OP", "^"):
            self.consume()
            exp = self.parse_exponent()
            base = tuple(v * exp for v in base)
        return base

    def parse_factor(self) -> tuple[Fraction, ...]:
        nxt = self.peek()
        if nxt is None:
            raise UnitError(f"Expected unit factor in {self.raw!r}.")
        if nxt == ("OP", "("):
            self.consume()
            inner = self.parse_expr()
            if self.peek() != ("OP", ")"):
                raise UnitError(f"Unclosed parenthesis in unit expression {self.raw!r}.")
            self.consume()
            return inner
        if nxt[0] == "NUM":
            val = self.consume()[1]
            if val in ("1", "+1"):
                return (Fraction(0),) * len(DIMENSIONS)
            raise UnitError(f"Unexpected numeric factor {val!r} in unit expression {self.raw!r}.")
        if nxt[0] == "ID":
            ident = self.consume()[1]
            if ident not in _UNIT_TABLE:
                raise UnitError(f"Unknown unit {ident!r} in expression {self.raw!r}.")
            return tuple(Fraction(x) for x in _UNIT_TABLE[ident])
        raise UnitError(f"Unexpected token {nxt[1]!r} in unit expression {self.raw!r}.")

    def parse_exponent(self) -> Fraction:
        nxt = self.peek()
        if nxt is None:
            raise UnitError(f"Missing exponent after '^' in {self.raw!r}.")
        if nxt == ("OP", "("):
            self.consume()
            num = self._parse_signed_rational()
            if self.peek() != ("OP", ")"):
                raise UnitError(f"Unclosed exponent parenthesis in {self.raw!r}.")
            self.consume()
            return num
        return self._parse_signed_rational(allow_slash=False)

    def _parse_signed_rational(self, allow_slash: bool = True) -> Fraction:
        sign = Fraction(1)
        nxt = self.peek()
        if nxt is not None and nxt[0] == "OP" and nxt[1] in ("+", "-"):
            if self.consume()[1] == "-":
                sign = Fraction(-1)
        tok = self.consume()
        if tok[0] != "NUM":
            raise UnitError(f"Invalid exponent {tok[1]!r} in {self.raw!r}.")
        try:
            val = sign * Fraction(tok[1])
        except (ValueError, ZeroDivisionError) as exc:
            raise UnitError(f"Invalid rational exponent {tok[1]!r} in {self.raw!r}.") from exc
        if allow_slash and self.peek() == ("OP", "/"):
            self.consume()
            den_tok = self.consume()
            if den_tok[0] != "NUM":
                raise UnitError(f"Invalid exponent denominator {den_tok[1]!r} in {self.raw!r}.")
            try:
                den = Fraction(den_tok[1])
                if den == 0:
                    raise UnitError(f"Zero denominator in exponent of {self.raw!r}.")
                val = val / den
            except ZeroDivisionError as exc:
                raise UnitError(f"Zero denominator in exponent of {self.raw!r}.") from exc
        return val


def parse_unit(expr: str) -> tuple[Fraction, ...]:
    """Parse a physical unit expression into a 6-tuple of exact rational exponents over DIMENSIONS."""
    if not isinstance(expr, str) or not expr.strip():
        raise UnitError("Unit expression must be a non-empty string.")
    tokens = _tokenize_unit(expr.strip())
    if not tokens:
        raise UnitError("Unit expression must be a non-empty string.")
    parser = _UnitParser(tokens, expr)
    vec = parser.parse_expr()
    if parser.peek() is not None:
        raise UnitError(f"Trailing token {parser.peek()} in unit expression {expr!r}.")
    return vec


def check_dimensional_homogeneity(lhs_unit: str, rhs_unit: str) -> bool:
    """Return True if and only if lhs_unit and rhs_unit have identical base dimensions."""
    return parse_unit(lhs_unit) == parse_unit(rhs_unit)


def _rref_fraction(matrix: list[list[Fraction]]) -> tuple[list[list[Fraction]], list[int]]:
    """Compute exact Reduced Row Echelon Form over Q; return (rref_matrix, pivot_columns)."""
    rows = len(matrix)
    cols = len(matrix[0]) if rows else 0
    mat = [[Fraction(x) for x in row] for row in matrix]
    pivots: list[int] = []
    r = 0
    for c in range(cols):
        if r >= rows:
            break
        pivot_row = next((i for i in range(r, rows) if mat[i][c] != 0), None)
        if pivot_row is None:
            continue
        mat[r], mat[pivot_row] = mat[pivot_row], mat[r]
        piv_val = mat[r][c]
        mat[r] = [v / piv_val for v in mat[r]]
        for i in range(rows):
            if i != r and mat[i][c] != 0:
                factor = mat[i][c]
                mat[i] = [mat[i][j] - factor * mat[r][j] for j in range(cols)]
        pivots.append(c)
        r += 1
    return mat, pivots


def _lcm_int(a: int, b: int) -> int:
    return abs(a * b) // math.gcd(a, b) if a and b else max(abs(a), abs(b), 1)


def _format_monomial(order: list[str], exponents: dict[str, Fraction]) -> str:
    parts: list[str] = []
    for name in order:
        exp = exponents[name]
        if exp == 0:
            continue
        if exp == 1:
            parts.append(name)
        elif exp.denominator == 1:
            parts.append(f"{name}^{exp.numerator}")
        else:
            parts.append(f"{name}^({exp.numerator}/{exp.denominator})")
    return " * ".join(parts) if parts else "1"


def buckingham_pi(
    variables: dict[str, str],
    target: str | None = None,
) -> list[dict[str, Any]]:
    """Compute exact rational Buckingham Pi dimensionless groups over Q."""
    if not variables and not (target and "=" in target):
        raise UnitError("buckingham_pi requires at least one variable.")
    vars_map: dict[str, str] = dict(variables)
    target_name: str | None = None
    if target is not None:
        raw_t = target.strip()
        if not raw_t:
            raise UnitError("target cannot be blank.")
        if "=" in raw_t:
            t_name, t_unit = raw_t.split("=", 1)
            t_name, t_unit = t_name.strip(), t_unit.strip()
            if not t_name or not t_unit:
                raise UnitError(f"Malformed target specification {target!r}; expected 'name=unit'.")
            vars_map[t_name] = t_unit
            target_name = t_name
        else:
            if raw_t not in vars_map:
                raise UnitError(f"Target variable {raw_t!r} not found in variables.")
            target_name = raw_t

    if not vars_map:
        raise UnitError("buckingham_pi requires at least one variable.")

    parsed: dict[str, tuple[Fraction, ...]] = {name: parse_unit(unit) for name, unit in vars_map.items()}

    if target_name is not None:
        pred_names = [k for k in vars_map if k != target_name]
        t_vec = parsed[target_name]
        for dim_idx, dim_name in enumerate(DIMENSIONS):
            if t_vec[dim_idx] != 0 and all(parsed[p][dim_idx] == 0 for p in pred_names):
                raise UnitError(
                    f"No dimensionless combination can cancel base dimension '{dim_name}' of target '{target_name}'."
                )
        col_names = pred_names + [target_name]
        display_order = [target_name] + pred_names
    else:
        col_names = list(vars_map.keys())
        display_order = list(col_names)

    n_cols = len(col_names)
    dim_matrix: list[list[Fraction]] = [
        [parsed[col_names[c]][r] for c in range(n_cols)]
        for r in range(len(DIMENSIONS))
    ]
    rref, pivot_cols = _rref_fraction(dim_matrix)
    pivot_set = set(pivot_cols)
    free_cols = [c for c in range(n_cols) if c not in pivot_set]

    if target_name is not None:
        target_col = n_cols - 1
        if target_col in pivot_set:
            raise UnitError(
                f"No dimensionless combination of predictors can cancel the dimensions of target '{target_name}'."
            )
        free_cols = [target_col] + [c for c in free_cols if c != target_col]

    groups: list[dict[str, Any]] = []
    for idx, f_col in enumerate(free_cols, start=1):
        vec = [Fraction(0)] * n_cols
        vec[f_col] = Fraction(1)
        for row_idx, p_col in enumerate(pivot_cols):
            vec[p_col] = -rref[row_idx][f_col]

        is_target_group = target_name is not None and f_col == n_cols - 1
        if not is_target_group:
            denom_lcm = 1
            for val in vec:
                denom_lcm = _lcm_int(denom_lcm, val.denominator)
            vec = [val * denom_lcm for val in vec]
            num_gcd = 0
            for val in vec:
                num_gcd = math.gcd(num_gcd, abs(val.numerator))
            if num_gcd > 1:
                vec = [val / num_gcd for val in vec]
            first_nz = next((val for val in vec if val != 0), Fraction(1))
            if first_nz < 0:
                vec = [-val for val in vec]

        exp_by_name = {col_names[c]: vec[c] for c in range(n_cols)}
        exponents_str = {name: str(exp_by_name[name]) for name in display_order}
        groups.append(
            {
                "name": f"pi_{idx}",
                "exponents": exponents_str,
                "expr": _format_monomial(display_order, exp_by_name),
            }
        )
    return groups


# ---------------------------------------------------------------- symbolic discovery engine
def _solve_linear(design: list[list[float]], rhs: list[float], ridge: float = 1e-10) -> list[float] | None:
    """Solve normal equations (X^T X + ridge*I) beta = X^T y via partial-pivoting Gaussian elimination."""
    n = len(design)
    if n == 0 or len(rhs) != n:
        return None
    p = len(design[0])
    ata = [[0.0] * p for _ in range(p)]
    aty = [0.0] * p
    for row, y_val in zip(design, rhs):
        for i in range(p):
            ri = row[i]
            aty[i] += ri * y_val
            for j in range(i, p):
                ata[i][j] += ri * row[j]
    for i in range(p):
        for j in range(i):
            ata[i][j] = ata[j][i]
        ata[i][i] += ridge * max(1.0, ata[i][i])

    aug = [ata[i] + [aty[i]] for i in range(p)]
    for col in range(p):
        piv = max(range(col, p), key=lambda r: abs(aug[r][col]))
        if abs(aug[piv][col]) < 1e-15:
            return None
        aug[col], aug[piv] = aug[piv], aug[col]
        div = aug[col][col]
        for j in range(col, p + 1):
            aug[col][j] /= div
        for r in range(p):
            if r != col and aug[r][col] != 0.0:
                fac = aug[r][col]
                for j in range(col, p + 1):
                    aug[r][j] -= fac * aug[col][j]
    sol = [aug[i][p] for i in range(p)]
    if any(not math.isfinite(v) for v in sol):
        return None
    return sol


def _bic(y_true: list[float], y_pred: list[float], k_eff: float) -> float:
    """Additive Gaussian likelihood BIC evaluated strictly on the original target y-scale."""
    n = len(y_true)
    rss = sum((a - b) ** 2 for a, b in zip(y_true, y_pred))
    mse = max(rss / max(n, 1), 1e-30)
    return n * math.log(mse) + k_eff * math.log(max(n, 2))


def _rmse(y_true: list[float], y_pred: list[float]) -> float:
    n = len(y_true)
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(y_true, y_pred)) / max(n, 1))


def _r2(y_true: list[float], y_pred: list[float]) -> float:
    if not y_true:
        return 0.0
    mean_y = sum(y_true) / len(y_true)
    ss_tot = sum((y - mean_y) ** 2 for y in y_true)
    ss_res = sum((a - b) ** 2 for a, b in zip(y_true, y_pred))
    if ss_tot <= 1e-30:
        return 1.0 if ss_res <= 1e-30 else 0.0
    val = 1.0 - ss_res / ss_tot
    return max(-10.0, min(1.0, val))


def _clean_rows(rows: list[dict[str, Any]], cols: list[str]) -> list[dict[str, float]]:
    if len(rows) < 8:
        raise ConjectureError(
            f"Symbolic discovery requires at least 8 rows for a valid train/holdout split (got {len(rows)})."
        )
    cleaned: list[dict[str, float]] = []
    for idx, row in enumerate(rows, start=1):
        out: dict[str, float] = {}
        for col in cols:
            if col not in row or row[col] is None:
                raise ConjectureError(f"Row {idx} is missing value for column {col!r}.")
            try:
                val = float(row[col])
            except (TypeError, ValueError) as exc:
                raise ConjectureError(f"Row {idx} column {col!r} is non-numeric ({row[col]!r}).") from exc
            if not math.isfinite(val):
                raise ConjectureError(f"Row {idx} column {col!r} contains non-finite value ({row[col]!r}).")
            out[col] = val
        cleaned.append(out)
    return cleaned


def _split_train_holdout(
    rows: list[dict[str, float]],
    *,
    holdout_mode: str,
    holdout_fraction: float,
    sort_by: str | None,
    default_sort: str,
    seed: int,
) -> tuple[list[dict[str, float]], list[dict[str, float]], str]:
    if holdout_mode not in ("tail", "random"):
        raise ConjectureError(f"Unsupported holdout_mode {holdout_mode!r}; use 'tail' or 'random'.")
    if not (0.1 <= holdout_fraction <= 0.5):
        raise ConjectureError(f"holdout_fraction must lie in [0.1, 0.5], got {holdout_fraction}.")
    n = len(rows)
    n_hold = max(2, int(round(n * holdout_fraction)))
    n_train = n - n_hold
    if n_train < 4 or n_hold < 2:
        raise ConjectureError(
            f"Insufficient train/holdout split (train={n_train}, holdout={n_hold}); need at least 8 rows."
        )
    sort_col = sort_by or default_sort
    if holdout_mode == "tail":
        if sort_col not in rows[0]:
            raise ConjectureError(f"sort_by column {sort_col!r} not found in rows.")
        ordered = sorted(rows, key=lambda r: r[sort_col])
        return ordered[:n_train], ordered[n_train:], sort_col
    shuffled = list(rows)
    random.Random(seed).shuffle(shuffled)
    return shuffled[:n_train], shuffled[n_train:], sort_col


def _fmt_num(x: float) -> str:
    """Format a coefficient for expression text without silently collapsing small values.

    A tiny but real coefficient (e.g. 5.454e-10) must never be rendered as "0": values
    below 1e-6 are emitted in scientific notation so the magnitude survives in the text.
    """
    if x == 0.0:
        return "0"
    if abs(x) < 1e-6:
        return f"{x:.6e}"
    return f"{x:.6g}"


def _num(x: float) -> float:
    """Lossless JSON-friendly float via a round-trip through the shortest repr.

    Unlike round(x, ndigits), this preserves small coefficients such as 5.454e-10 exactly
    (Python's repr is guaranteed to round-trip), so sealed artifacts never collapse a
    meaningful parameter or metric to 0.0.
    """
    return float(repr(x))


def _pareto_frontier_internal(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Non-dominated candidates over (complexity_k, val_rmse) computed strictly inside train (never holdout)."""
    ordered = sorted(candidates, key=lambda c: (c["complexity_k"], c["val_rmse"]))
    frontier: list[dict[str, Any]] = []
    best_rmse = float("inf")
    for cand in ordered:
        if cand["val_rmse"] < best_rmse - 1e-12:
            frontier.append(
                {
                    "id": cand["id"],
                    "complexity_k": cand["complexity_k"],
                    "val_rmse": cand["val_rmse"],
                    "holdout_rmse": cand["holdout_rmse"],
                    "expr": cand["expr"],
                }
            )
            best_rmse = cand["val_rmse"]
    return frontier


def _discover_invariants(
    rows: list[dict[str, Any]],
    predictors: list[str],
    *,
    holdout_mode: str,
    holdout_fraction: float,
    sort_by: str | None,
    snap_rationals: bool,
    max_denom: int,
    seed: int,
    units: dict[str, str] | None = None,
    source_ids: list[str] | None = None,
    falsifier_at: dict[str, float] | None = None,
) -> dict[str, Any]:
    if len(predictors) < 2:
        raise ConjectureError("Invariant discovery (__invariant__) requires at least 2 predictor columns.")
    cleaned = _clean_rows(rows, predictors)
    train, holdout, sort_col = _split_train_holdout(
        cleaned,
        holdout_mode=holdout_mode,
        holdout_fraction=holdout_fraction,
        sort_by=sort_by,
        default_sort=predictors[0],
        seed=seed,
    )
    n_val = max(2, len(train) // 4) if len(train) >= 6 else 1
    train_sub, val_sub = train[: len(train) - n_val], train[len(train) - n_val :]

    def eval_invariant(
        dataset: list[dict[str, float]], fn: Callable[[dict[str, float]], float], scale_floor: float
    ) -> tuple[float, float]:
        vals = [fn(r) for r in dataset]
        if any(not math.isfinite(v) for v in vals):
            return float("inf"), 0.0
        mean_v = sum(vals) / len(vals)
        sd_v = math.sqrt(sum((v - mean_v) ** 2 for v in vals) / max(len(vals), 1))
        denom = max(abs(mean_v), scale_floor, 1e-12)
        return sd_v / denom, mean_v

    col_sds = [
        math.sqrt(sum((r[p] - sum(x[p] for x in train) / len(train)) ** 2 for r in train) / len(train))
        for p in predictors
    ]
    if max(col_sds) <= 1e-12:
        raise ConjectureError("All predictor columns have zero variance; no non-trivial invariant exists.")
    anchor_scale = max(col_sds[0], 1e-12)

    linear_dim_ok = True
    if units:
        parsed_dims = [parse_unit(units[p]) for p in predictors if p in units]
        if len(parsed_dims) == len(predictors) and len(set(parsed_dims)) > 1:
            linear_dim_ok = False

    raw_candidates: list[dict[str, Any]] = []
    # DIS-15 (documented anchor limitation): the linear and power-law invariant searches fix
    # predictors[0]'s weight at 1.0 (anchor), so only invariants that involve the first column are
    # discovered. Relations among the *other* columns (e.g. x2 + x3 = const with x1 unrelated) are
    # out of scope for this cheap pass; exponents are point estimates without a bootstrap CI.
    anchor = predictors[0]
    others = predictors[1:]

    # 1. Linear conservation fitted on train_sub for internal validation, refitted on full train for sealed holdout
    # Skipped when --units proves predictors have heterogeneous SI base dimensions (adding incompatible units is illegal).
    if linear_dim_ok:
        design_sub = [[1.0] + [r[p] for p in others] for r in train_sub]
        rhs_sub = [-r[anchor] for r in train_sub]
        beta_sub = _solve_linear(design_sub, rhs_sub)
        design_lin = [[1.0] + [r[p] for p in others] for r in train]
        rhs_lin = [-r[anchor] for r in train]
        beta_lin = _solve_linear(design_lin, rhs_lin)
    else:
        beta_sub = None
        beta_lin = None
    def _make_lin_fn(weights: dict[str, float]) -> Any:
        def _fn(row: dict[str, float]) -> float:
            return sum(weights[p] * row[p] for p in predictors)
        return _fn

    def _make_mono_fn(exps_f: dict[str, float]) -> Any:
        def _fn(row: dict[str, float]) -> float:
            return math.prod(row[p] ** exps_f[p] for p in predictors)
        return _fn

    if beta_sub is not None and beta_lin is not None:
        w_sub = {anchor: 1.0, **{p: beta_sub[i + 1] for i, p in enumerate(others)}}
        val_cv, _ = eval_invariant(val_sub, _make_lin_fn(w_sub), anchor_scale)
        weights_free = {anchor: 1.0, **{p: beta_lin[i + 1] for i, p in enumerate(others)}}
        tr_cv, tr_mean = eval_invariant(train, _make_lin_fn(weights_free), anchor_scale)
        ho_cv, _ = eval_invariant(holdout, _make_lin_fn(weights_free), anchor_scale)
        terms = [f"{_fmt_num(weights_free[p])} * {p}" if weights_free[p] != 1.0 else p for p in predictors if abs(weights_free[p]) > 1e-9]
        raw_candidates.append(
            {
                "family": "linear_invariant",
                "expr": f"{' + '.join(terms)} = {_fmt_num(tr_mean)}",
                "exponents": {},
                "parameters": {**{f"w_{p}": _num(weights_free[p]) for p in predictors}, "constant": _num(tr_mean)},
                "complexity_k": len(predictors),
                "_k_eff": float(len(predictors)),
                "train_bic": len(train) * math.log(max(tr_cv ** 2, 1e-30)) + len(predictors) * math.log(len(train)),
                "val_rmse": _num(val_cv),
                "holdout_rmse": _num(ho_cv),
                "holdout_r2": _num(max(0.0, 1.0 - ho_cv ** 2)),
            }
        )
        if snap_rationals:
            snapped_w: dict[str, Fraction] = {anchor: Fraction(1)}
            for i, p in enumerate(others):
                snapped_w[p] = Fraction(beta_lin[i + 1]).limit_denominator(max_denom)
            if any(snapped_w[p] != 0 for p in others):
                snapped_w_f = {p: float(snapped_w[p]) for p in predictors}
                val_cv_s, _ = eval_invariant(val_sub, _make_lin_fn(snapped_w_f), anchor_scale)
                tr_cv_s, tr_mean_s = eval_invariant(train, _make_lin_fn(snapped_w_f), anchor_scale)
                ho_cv_s, _ = eval_invariant(holdout, _make_lin_fn(snapped_w_f), anchor_scale)
                s_terms = [p if snapped_w[p] == 1 else f"({snapped_w[p]}) * {p}" for p in predictors if snapped_w[p] != 0]
                raw_candidates.append(
                    {
                        "family": "linear_invariant_rational",
                        "expr": f"{' + '.join(s_terms)} = {_fmt_num(tr_mean_s)}",
                        "exponents": {p: str(snapped_w[p]) for p in predictors},
                        "parameters": {"constant": _num(tr_mean_s)},
                        "complexity_k": 2,
                        "_k_eff": 1.5,
                        "train_bic": len(train) * math.log(max(tr_cv_s ** 2, 1e-30)) + 1.5 * math.log(len(train)),
                        "val_rmse": _num(val_cv_s),
                        "holdout_rmse": _num(ho_cv_s),
                        "holdout_r2": _num(max(0.0, 1.0 - ho_cv_s ** 2)),
                    }
                )

    # 2. Power-law product invariant on positive columns
    if all(r[p] > 0.0 for r in cleaned for p in predictors):
        seen_monomial_exps: set[tuple[tuple[str, str], ...]] = set()

        def _append_monomial(exps: dict[str, Fraction]) -> None:
            sig = tuple((p, str(exps[p])) for p in predictors)
            if sig in seen_monomial_exps or not any(exps[p] != 0 for p in others):
                return
            seen_monomial_exps.add(sig)
            exps_f = {p: float(exps[p]) for p in predictors}
            mono_fn = _make_mono_fn(exps_f)
            val_cv_p, _ = eval_invariant(val_sub, mono_fn, 1e-12)
            tr_cv_p, tr_mean_p = eval_invariant(train, mono_fn, 1e-12)
            ho_cv_p, _ = eval_invariant(holdout, mono_fn, 1e-12)
            if math.isfinite(tr_cv_p) and math.isfinite(ho_cv_p):
                raw_candidates.append(
                    {
                        "family": "monomial_invariant",
                        "expr": f"{_format_monomial(predictors, exps)} = {_fmt_num(tr_mean_p)}",
                        "exponents": {p: str(exps[p]) for p in predictors},
                        "parameters": {"constant": _num(tr_mean_p)},
                        "complexity_k": 2,
                        "_k_eff": 1.5,
                        "train_bic": len(train) * math.log(max(tr_cv_p ** 2, 1e-30)) + 1.5 * math.log(len(train)),
                        "val_rmse": _num(val_cv_p),
                        "holdout_rmse": _num(ho_cv_p),
                        "holdout_r2": _num(max(0.0, 1.0 - ho_cv_p ** 2)),
                    }
                )

        if units and all(p in units for p in predictors):
            try:
                pi_groups = buckingham_pi({p: units[p] for p in predictors}, target=anchor)
            except ConjectureError:
                pi_groups = []
            for grp in pi_groups:
                g_exps = {p: Fraction(grp["exponents"].get(p, "0")) for p in predictors}
                if g_exps.get(anchor, Fraction(0)) != 0:
                    norm_e = {p: g_exps[p] / g_exps[anchor] for p in predictors}
                    _append_monomial(norm_e)

        design_log = [[1.0] + [math.log(r[p]) for p in others] for r in train]
        rhs_log = [-math.log(r[anchor]) for r in train]
        beta_log = _solve_linear(design_log, rhs_log)
        if beta_log is not None and snap_rationals:
            snapped_e: dict[str, Fraction] = {anchor: Fraction(1)}
            for i, p in enumerate(others):
                snapped_e[p] = Fraction(beta_log[i + 1]).limit_denominator(max_denom)
            _append_monomial(snapped_e)

    if not raw_candidates:
        raise ConjectureError("No finite candidate invariants could be fitted on the supplied columns.")

    # Rank strictly by internal (val_rmse, train_bic, complexity_k) — never holdout!
    raw_candidates.sort(key=lambda c: (c["val_rmse"], c["train_bic"], c["complexity_k"]))
    candidates: list[dict[str, Any]] = []
    for i, cand in enumerate(raw_candidates[:6], start=1):
        cand_clean = {k: v for k, v in cand.items() if not k.startswith("_")}
        cand_clean["id"] = f"C_INV_{i}"
        cand_clean["train_bic"] = _num(float(cand_clean["train_bic"]))
        candidates.append(cand_clean)

    best = candidates[0]
    rng = random.Random(seed)
    surrogate_cvs: list[float] = []
    for _ in range(20):
        shuffled_rows = [dict(r) for r in cleaned]
        for p in others:
            col_vals = [r[p] for r in cleaned]
            rng.shuffle(col_vals)
            for i, val in enumerate(col_vals):
                shuffled_rows[i][p] = val
        s_tr, s_ho = shuffled_rows[: len(train)], shuffled_rows[len(train) :]
        if best["family"] == "monomial_invariant":
            exps = {p: float(Fraction(best["exponents"][p])) for p in predictors}
            cv_s, _ = eval_invariant(s_ho, _make_mono_fn(exps), 1e-12)
            if math.isfinite(cv_s):
                surrogate_cvs.append(cv_s)
        else:
            s_des = [[1.0] + [r[p] for p in others] for r in s_tr]
            s_rhs = [-r[anchor] for r in s_tr]
            s_b = _solve_linear(s_des, s_rhs)
            if s_b is not None:
                w_s = {anchor: 1.0, **{p: s_b[i + 1] for i, p in enumerate(others)}}
                cv_s, _ = eval_invariant(s_ho, _make_lin_fn(w_s), anchor_scale)
                if math.isfinite(cv_s):
                    surrogate_cvs.append(cv_s)
    null_cv = statistics.median(surrogate_cvs) if surrogate_cvs else 1.0
    beats_null = bool(best["holdout_rmse"] < min(0.15, 0.2 * null_cv))

    # N3: the falsifier tolerance is RELATIVE. The invariant metric is already a relative SD
    # (sd/mean), so the floor is a documented relative-SD floor (1e-6), never a unitful absolute
    # 1e-4. Warn when that tolerance is thinner than ~100 ULP of the invariant constant.
    inv_warnings: list[str] = []
    ho_rmse = float(best["holdout_rmse"])
    falsifier_tol = max(ho_rmse * 3.0, 1e-6)
    const_abs = 1.0
    best_params = best.get("parameters")
    if isinstance(best_params, dict):
        try:
            c = float(best_params.get("constant", 0.0))
        except (TypeError, ValueError):
            c = 0.0
        if c != 0.0 and math.isfinite(c):
            const_abs = abs(c)
    if const_abs > 0.0:
        ulp_rel = 100.0 * math.ulp(const_abs) / const_abs
        if falsifier_tol < ulp_rel:
            inv_warnings.append(
                f"Invariant falsifier tolerance {falsifier_tol:.3g} (relative SD) is below ~100 ULP of the "
                f"invariant constant ({const_abs:.6g}); the tolerance is at machine precision."
            )

    # DIS-2: use the observed min/max of the sort column, not the input-ordered first/last rows.
    sort_min = min(r[sort_col] for r in cleaned)
    sort_max = max(r[sort_col] for r in cleaned)

    # DIS-4: build a falsifier point for schema parity with discover; honor --falsifier-at when given.
    falsifier_point: dict[str, float] = {
        p: float(statistics.median(r[p] for r in train)) for p in predictors
    }
    falsifier_point[sort_col] = float(sort_max * 1.5 if sort_max > 0 else sort_max + 1.0)
    if falsifier_at:
        for fk, fv in falsifier_at.items():
            if fk not in predictors:
                raise ConjectureError(f"falsifier_at column {fk!r} is not in predictors {predictors!r}.")
            falsifier_point[fk] = float(fv)
    point_str = ", ".join(f"{p}={falsifier_point[p]:.4g}" for p in predictors)

    return {
        "target": "__invariant__",
        "predictors": list(predictors),
        "units": dict(units) if units is not None else None,
        "source_ids": [str(s).strip() for s in (source_ids or []) if str(s).strip()],
        "likelihood_scale": "invariant_relative_sd",
        "n_candidates_evaluated": len(raw_candidates),
        "sort_by": sort_col,
        "holdout_mode": holdout_mode,
        "train_count": len(train),
        "holdout_count": len(holdout),
        "null_holdout_rmse": _num(float(null_cv)),
        "beats_null": beats_null,
        "warnings": inv_warnings,
        "candidates": candidates,
        "pareto_frontier": _pareto_frontier_internal(candidates),
        "falsifier_point": falsifier_point,
        "falsifier_prediction": (
            f"Along an independent trajectory outside {sort_col} in [{sort_min:.4g}, {sort_max:.4g}] "
            f"(falsifier point: {point_str}), "
            f"invariant '{best['expr']}' must hold within relative SD <= {falsifier_tol:.4g}."
        ),
    }


def _is_candidate_dimensionally_consistent(
    family: str,
    exps: dict[str, str],
    target: str,
    predictors: list[str],
    parsed_units: dict[str, tuple[Fraction, ...]] | None,
) -> bool | None:
    """Dimensional consistency for a fitted candidate, or None when the family has no
    dimensionless-exponent interpretation to evaluate (``not evaluated``, distinct from ``False``)."""
    if parsed_units is None:
        return None
    if family in ("buckingham_pi_monomial", "buckingham_pi_power"):
        return True
    t_vec = parsed_units[target]
    zero_vec = (Fraction(0),) * len(DIMENSIONS)
    if family == "null_constant":
        return t_vec == zero_vec

    # Monomial families: prod(p^e_p) must have exactly the target's base dimension (so the
    # leading constant is a pure dimensionless scale). shifted_power carries a real exponent
    # {col: -a}, so it is checked the same way as power_law.
    if family in ("power_law", "power_law_rational", "shifted_power"):
        if not exps:
            return False
        rhs_vec = list(zero_vec)
        for p, raw_e in exps.items():
            if p not in parsed_units:
                return False
            try:
                q_e = Fraction(raw_e)
            except (ValueError, ZeroDivisionError):
                return False
            p_vec = parsed_units[p]
            for d_idx in range(len(DIMENSIONS)):
                rhs_vec[d_idx] += q_e * p_vec[d_idx]
        return tuple(rhs_vec) == t_vec

    # Additive linear laws y = c0 + sum(c_i * x_i) are dimensionally homogeneous only when every
    # involved predictor carries the same base dimension as the target (add like quantities).
    if family in ("linear", "linear_2var"):
        involved = [p for p in exps if p in parsed_units]
        if not involved:
            return None
        return all(parsed_units[p] == t_vec for p in involved)

    # Families with no dimensionless-exponent interpretation (inverse_log, exponential,
    # rational_ratio) are genuinely "not evaluated" rather than "known inconsistent".
    return None


def discover_laws(
    rows: list[dict[str, float]],
    target: str,
    predictors: list[str],
    *,
    units: dict[str, str] | None = None,
    holdout_mode: str = "tail",
    holdout_fraction: float = 0.25,
    sort_by: str | None = None,
    snap_rationals: bool = True,
    max_denom: int = 8,
    seed: int = 0,
    source_ids: list[str] | None = None,
    falsifier_at: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Discover parsimonious candidate laws using internal validation inside train and a single sealed holdout check."""
    if not predictors:
        raise ConjectureError("predictors must contain at least one column name.")
    if target == "__invariant__":
        return _discover_invariants(
            rows,
            predictors,
            holdout_mode=holdout_mode,
            holdout_fraction=holdout_fraction,
            sort_by=sort_by,
            snap_rationals=snap_rationals,
            max_denom=max_denom,
            seed=seed,
            units=units,
            source_ids=source_ids,
            falsifier_at=falsifier_at,
        )
    if target in predictors:
        raise ConjectureError(f"target {target!r} cannot also appear in predictors.")

    all_cols = list(predictors) + [target]
    clean_cols = list(all_cols) + ([sort_by] if sort_by and sort_by not in all_cols else [])
    cleaned = _clean_rows(rows, clean_cols)
    y_all = [r[target] for r in cleaned]
    # DIS-12: use the same RELATIVE zero-variance threshold as the predictor guard below.
    if max(y_all) - min(y_all) <= 1e-15 * max(1.0, abs(y_all[0])):
        raise ConjectureError(f"Target column {target!r} has zero variance.")

    pi_groups: list[dict[str, Any]] | None = None
    parsed_units: dict[str, tuple[Fraction, ...]] | None = None
    if units is not None:
        missing_u = [c for c in all_cols if c not in units]
        if missing_u:
            raise UnitError(f"Missing unit specification for column(s): {', '.join(missing_u)}.")
        parsed_units = {c: parse_unit(units[c]) for c in all_cols}
        pred_units = {p: units[p] for p in predictors}
        pi_groups = buckingham_pi(pred_units, target=f"{target}={units[target]}")

    train, holdout, sort_col = _split_train_holdout(
        cleaned,
        holdout_mode=holdout_mode,
        holdout_fraction=holdout_fraction,
        sort_by=sort_by,
        default_sort=predictors[0],
        seed=seed,
    )
    warnings_list: list[str] = []
    if len(train) < 10:
        warnings_list.append(
            f"Small training partition (train_count={len(train)}, fewer than 10 rows; holdout_count={len(holdout)}); "
            f"cross-validation and holdout metrics have high sampling variance."
        )

    varying_predictors: list[str] = []
    for p in predictors:
        p_vals = [r[p] for r in train]
        if max(p_vals) - min(p_vals) <= 1e-15 * max(1.0, abs(p_vals[0])):
            warnings_list.append(
                f"Predictor {p!r} has zero variance on the training partition; its exponent cannot be identified from data alone (only by dimensional constraint)."
            )
        else:
            varying_predictors.append(p)
    # DIS-3: never re-include constant predictors. If nothing varies, fit only the null model
    # (and the dimensional Pi families when --units is given) instead of emitting spurious slopes.
    if not varying_predictors:
        warnings_list.append(
            "All predictors have zero variance on the training partition; only the null model "
            "(and dimensional Pi families, if --units is given) will be fitted."
        )
    free_predictors = list(varying_predictors)

    n_folds = min(5, max(2, len(train) // 2))
    folds: list[tuple[list[dict[str, float]], list[float], list[dict[str, float]], list[int]]] = []
    for fi in range(n_folds):
        lo = (fi * len(train)) // n_folds
        hi = ((fi + 1) * len(train)) // n_folds
        if hi <= lo:
            continue
        f_tr = train[:lo] + train[hi:]
        f_va = train[lo:hi]
        if len(f_tr) >= 3 and len(f_va) >= 1:
            folds.append((f_tr, [r[target] for r in f_tr], f_va, list(range(lo, hi))))

    y_tr = [r[target] for r in train]
    y_ho = [r[target] for r in holdout]
    mean_tr_init = sum(y_tr) / len(y_tr)
    ho_fallback_rmse = max(_rmse(y_ho, [mean_tr_init] * len(y_ho)) * 1e6, 1.0)

    # DIS-1: with train_count 4-5 the k-fold loop above can silently skip folds (len(f_tr) < 3),
    # leaving oof_preds at 0.0 sentinels for uncovered rows. Fall back to leave-one-out so every
    # training row receives exactly one out-of-fold prediction; never rank against an all-zero vector.
    covered = {idx for _, _, _, idxs in folds for idx in idxs}
    if covered != set(range(len(train))):
        warnings_list.append(
            f"k-fold cross-validation could not cover all {len(train)} training rows "
            f"(covered {len(covered)}); falling back to leave-one-out so out-of-fold metrics stay well-defined."
        )
        folds = [
            (train[:i] + train[i + 1 :], y_tr[:i] + y_tr[i + 1 :], [train[i]], [i])
            for i in range(len(train))
        ]

    raw_candidates: list[dict[str, Any]] = []

    def evaluate_and_add(
        family: str,
        fit_fn: Callable[[list[dict[str, float]], list[float]], tuple[str, Callable[[dict[str, float]], float], dict[str, str], dict[str, float]] | None],
        complexity_k: int,
        k_eff: float,
    ) -> None:
        full_fit = fit_fn(train, y_tr)
        if full_fit is None:
            return
        expr, pred_fn_full, exps, params = full_fit
        oof_preds = [0.0] * len(train)
        for f_tr, f_y, f_va, idxs in folds:
            fold_fit = fit_fn(f_tr, f_y)
            if fold_fit is None:
                return
            _, fn_fold, _, _ = fold_fit
            try:
                for idx_local, row_va in zip(idxs, f_va):
                    oof_preds[idx_local] = fn_fold(row_va)
            except (ValueError, ZeroDivisionError, OverflowError):
                return
        try:
            pred_tr = [pred_fn_full(r) for r in train]
        except (ValueError, ZeroDivisionError, OverflowError):
            return
        if any(isinstance(v, complex) or not math.isfinite(v) for v in oof_preds) or any(
            isinstance(v, complex) or not math.isfinite(v) for v in pred_tr
        ):
            return

        # Holdout is evaluated AFTER candidate admissibility is decided solely on train/oof (never filters raw_candidates!)
        holdout_valid = True
        try:
            pred_ho = [pred_fn_full(r) for r in holdout]
            if any(isinstance(v, complex) or not math.isfinite(v) for v in pred_ho):
                holdout_valid = False
                pred_ho = []
        except (TypeError, ValueError, ZeroDivisionError, OverflowError):
            holdout_valid = False
            pred_ho = []

        tr_bic = _bic(y_tr, pred_tr, k_eff)
        val_bic = _bic(y_tr, oof_preds, k_eff)
        val_rmse = _rmse(y_tr, oof_preds)
        ho_rmse = _rmse(y_ho, pred_ho) if holdout_valid else ho_fallback_rmse
        ho_r2 = _r2(y_ho, pred_ho) if holdout_valid else -10.0
        dim_ok = _is_candidate_dimensionally_consistent(family, exps, target, predictors, parsed_units)
        cand_entry: dict[str, Any] = {
            "family": family,
            "expr": expr,
            "exponents": exps,
            "parameters": params,
            "complexity_k": complexity_k,
            "dimensionally_consistent": dim_ok,
            "_k_eff": k_eff,
            "_val_bic": val_bic,
            "_holdout_valid": holdout_valid,
            "_pred_fn": pred_fn_full,
            "train_bic": _num(tr_bic),
            "val_rmse": _num(val_rmse),
            "holdout_rmse": _num(ho_rmse),
            "holdout_r2": _num(ho_r2),
        }
        raw_candidates.append(cand_entry)

    # Null constant model y = c0
    def _fit_null(ds: list[dict[str, float]], ys: list[float]) -> tuple[str, Callable[[dict[str, float]], float], dict[str, str], dict[str, float]]:
        m = sum(ys) / len(ys)
        return f"{target} = {_fmt_num(m)}", (lambda _r, c=m: c), {}, {"c0": _num(m)}

    evaluate_and_add("null_constant", _fit_null, complexity_k=1, k_eff=1.0)
    null_cand = raw_candidates[0]
    null_train_bic = float(null_cand["train_bic"])
    null_val_bic = float(null_cand["_val_bic"])
    null_val_rmse = float(null_cand["val_rmse"])
    null_holdout_rmse = float(null_cand["holdout_rmse"])

    if pi_groups is not None:
        g0 = pi_groups[0]
        base_exps = {p: -Fraction(g0["exponents"][p]) for p in predictors}
        pi_required = [p for p in predictors if base_exps[p] != 0]
        # DIS-9: skip (never raise) the Pi families when a dimensionally required predictor has
        # non-positive values. The guard covers the full dataset (train + holdout) so non-positive
        # holdout rows are handled explicitly rather than surfacing later as a complex/ValueError.
        skip_pi = not all(r[p] > 0.0 for r in cleaned for p in pi_required)
        if skip_pi:
            warnings_list.append(
                "Dimensionally required predictor(s) contain non-positive values in train or holdout; "
                f"skipping Buckingham Pi families (required positive for {pi_required!r}). "
                "Other data-driven families are still evaluated."
            )

        def _fit_pi_mono(
            ds: list[dict[str, float]], ys: list[float]
        ) -> tuple[str, Callable[[dict[str, float]], float], dict[str, str], dict[str, float]] | None:
            zs = [math.prod((r[p] ** float(base_exps[p])) if base_exps[p] != 0 else 1.0 for p in predictors) for r in ds]
            den = sum(z * z for z in zs)
            if den <= 1e-30:
                return None
            c0 = sum(z * y for z, y in zip(zs, ys)) / den
            mono_str = _format_monomial(predictors, base_exps)
            expr = f"{target} = {_fmt_num(c0)} * {mono_str}" if mono_str != "1" else f"{target} = {_fmt_num(c0)}"
            return (
                expr,
                (lambda r, c=c0: c * math.prod((r[p] ** float(base_exps[p])) if base_exps[p] != 0 else 1.0 for p in predictors)),
                {p: str(base_exps[p]) for p in predictors},
                {"c0": _num(c0)},
            )

        if not skip_pi:
            evaluate_and_add("buckingham_pi_monomial", _fit_pi_mono, complexity_k=2, k_eff=1.5)

        if not skip_pi and len(pi_groups) >= 2 and all(r[p] > 0.0 for r in train for p in predictors) and all(y > 0.0 for y in y_tr):
            pi_exps_list: list[dict[str, Fraction]] = []
            for g in pi_groups[1:]:
                ge = {p: Fraction(g["exponents"][p]) for p in predictors}
                # Only include pi groups whose log varies across train rows
                g_vals = [math.log(math.prod((r[p] ** float(ge[p])) if ge[p] != 0 else 1.0 for p in predictors)) for r in train]
                if max(g_vals) - min(g_vals) > 1e-12:
                    pi_exps_list.append(ge)

            if pi_exps_list:
                def _fit_pi_power(
                    ds: list[dict[str, float]], ys: list[float]
                ) -> tuple[str, Callable[[dict[str, float]], float], dict[str, str], dict[str, float]] | None:
                    z_base = [math.prod((r[p] ** float(base_exps[p])) if base_exps[p] != 0 else 1.0 for p in predictors) for r in ds]
                    des = [
                        [1.0] + [math.log(math.prod((r[p] ** float(ge[p])) if ge[p] != 0 else 1.0 for p in predictors)) for ge in pi_exps_list]
                        for r in ds
                    ]
                    rhs = [math.log(y / z) for y, z in zip(ys, z_base)]
                    beta = _solve_linear(des, rhs)
                    if beta is None:
                        return None
                    tot: dict[str, Fraction] = dict(base_exps)
                    for gi, ge in enumerate(pi_exps_list):
                        qb = Fraction(beta[gi + 1]).limit_denominator(max_denom) if snap_rationals else Fraction(beta[gi + 1])
                        for p in predictors:
                            tot[p] += qb * ge[p]
                    zt = [math.prod((r[p] ** float(tot[p])) if tot[p] != 0 else 1.0 for p in predictors) for r in ds]
                    d2 = sum(z * z for z in zt)
                    if d2 <= 1e-30:
                        return None
                    c0 = sum(z * y for z, y in zip(zt, ys)) / d2
                    mono2 = _format_monomial(predictors, tot)
                    return (
                        f"{target} = {_fmt_num(c0)} * {mono2}",
                        (lambda r, c=c0, te=tot: c * math.prod((r[p] ** float(te[p])) if te[p] != 0 else 1.0 for p in predictors)),
                        {p: str(tot[p]) for p in predictors},
                        {"c0": _num(c0)},
                    )

                evaluate_and_add("buckingham_pi_power", _fit_pi_power, complexity_k=2, k_eff=2.0)

    # B1 fix: ALWAYS evaluate data-driven families on varying predictors alongside Buckingham Pi families
    # 1. Linear models
    for p_col in free_predictors:
        def _make_lin(col: str) -> Callable[[list[dict[str, float]], list[float]], Any]:
            def _fit(ds: list[dict[str, float]], ys: list[float]) -> Any:
                b = _solve_linear([[1.0, r[col]] for r in ds], ys)
                if b is None:
                    return None
                c0, c1 = b
                return (
                    f"{target} = {_fmt_num(c0)} + {_fmt_num(c1)} * {col}",
                    (lambda r, a=c0, m=c1, k=col: a + m * r[k]),
                    {col: "1"},
                    {"c0": _num(c0), "c1": _num(c1)},
                )
            return _fit

        evaluate_and_add("linear", _make_lin(p_col), complexity_k=2, k_eff=2.0)

    if len(free_predictors) >= 2:
        for i in range(len(free_predictors)):
            for j in range(i + 1, min(len(free_predictors), i + 4)):
                p1, p2 = free_predictors[i], free_predictors[j]

                def _make_lin2(c_a: str, c_b: str) -> Callable[[list[dict[str, float]], list[float]], Any]:
                    def _fit(ds: list[dict[str, float]], ys: list[float]) -> Any:
                        b = _solve_linear([[1.0, r[c_a], r[c_b]] for r in ds], ys)
                        if b is None:
                            return None
                        b0, b1, b2 = b
                        return (
                            f"{target} = {_fmt_num(b0)} + {_fmt_num(b1)} * {c_a} + {_fmt_num(b2)} * {c_b}",
                            (lambda r, x0=b0, x1=b1, x2=b2, ka=c_a, kb=c_b: x0 + x1 * r[ka] + x2 * r[kb]),
                            {c_a: "1", c_b: "1"},
                            {"c0": _num(b0), "c1": _num(b1), "c2": _num(b2)},
                        )
                    return _fit

                evaluate_and_add("linear_2var", _make_lin2(p1, p2), complexity_k=3, k_eff=3.0)

    # 2. Power laws (positive domain on train — never peeks at holdout!)
    pos_y = all(y > 0.0 for y in y_tr)
    pos_preds = [p for p in free_predictors if all(r[p] > 0.0 for r in train)]
    if pos_y and pos_preds:
        subsets: list[list[str]] = [[p] for p in pos_preds]
        if len(pos_preds) >= 2:
            # DIS-15 (documented truncation): the multi-variable power law is limited to the first
            # 4 positive predictors to bound the combinatorial search for wide tables.
            subsets.append(pos_preds[:4])
        for sub_p in subsets:
            def _make_pl_free(cols: list[str]) -> Callable[[list[dict[str, float]], list[float]], Any]:
                def _fit(ds: list[dict[str, float]], ys: list[float]) -> Any:
                    b = _solve_linear([[1.0] + [math.log(r[p]) for p in cols] for r in ds], [math.log(y) for y in ys])
                    if b is None:
                        return None
                    alphas = [b[idx + 1] for idx in range(len(cols))]
                    if any(abs(a) > 12.0 for a in alphas):
                        return None
                    zs = [math.prod(r[p] ** a for p, a in zip(cols, alphas)) for r in ds]
                    den = sum(z * z for z in zs)
                    if den <= 1e-30:
                        return None
                    c0 = sum(z * y for z, y in zip(zs, ys)) / den
                    exp_terms = " * ".join(f"{p}^{_fmt_num(a)}" for p, a in zip(cols, alphas))
                    return (
                        f"{target} = {_fmt_num(c0)} * {exp_terms}",
                        (lambda r, c=c0, cs=cols, al=alphas: c * math.prod(r[p] ** a for p, a in zip(cs, al))),
                        {p: _fmt_num(a) for p, a in zip(cols, alphas)},
                        {"c0": _num(c0)},
                    )
                return _fit

            k_free = 1 + len(sub_p)
            evaluate_and_add("power_law", _make_pl_free(sub_p), complexity_k=k_free, k_eff=float(k_free))

            if snap_rationals:
                b_tr_pl = _solve_linear(
                    [[1.0] + [math.log(r[p]) for p in sub_p] for r in train],
                    [math.log(y) for y in y_tr],
                )
                if b_tr_pl is not None:
                    seen_q: set[tuple[Fraction, ...]] = set()
                    denoms = sorted({min(4, max_denom), max_denom})
                    for d_lim in denoms:
                        q_vec = tuple(Fraction(b_tr_pl[idx + 1]).limit_denominator(d_lim) for idx in range(len(sub_p)))
                        if q_vec in seen_q:
                            continue
                        seen_q.add(q_vec)
                        snapped_map = {p: q for p, q in zip(sub_p, q_vec)}
                        active_map = {p: q for p, q in snapped_map.items() if q != 0 and abs(q) <= 12}
                        if not active_map:
                            continue

                        def _make_fixed_rational(
                            cols: list[str],
                            s_map: dict[str, Fraction],
                            act: dict[str, Fraction],
                        ) -> Callable[[list[dict[str, float]], list[float]], Any]:
                            full_exps = {p: s_map.get(p, Fraction(0)) for p in predictors}
                            mono_s = _format_monomial(list(act.keys()), act)
                            exp_dict = {p: str(full_exps[p]) for p in predictors if full_exps[p] != 0 or p in cols}

                            def _fit(ds: list[dict[str, float]], ys: list[float]) -> Any:
                                zs = [math.prod(r[p] ** float(q) for p, q in act.items()) for r in ds]
                                den = sum(z * z for z in zs)
                                if den <= 1e-30:
                                    return None
                                c0 = sum(z * y for z, y in zip(zs, ys)) / den
                                return (
                                    f"{target} = {_fmt_num(c0)} * {mono_s}",
                                    (lambda r, c=c0, a=act: c * math.prod(r[p] ** float(q) for p, q in a.items())),
                                    exp_dict,
                                    {"c0": _num(c0)},
                                )

                            return _fit

                        evaluate_and_add(
                            "power_law_rational",
                            _make_fixed_rational(sub_p, snapped_map, active_map),
                            complexity_k=2,
                            k_eff=2.0,
                        )

    # 3. Shifted asymptotic, inverse-log, and exponential forms (checked on train/ds only!)
    for p_col in free_predictors:
        if all(r[p_col] > 0.0 for r in train):
            for alpha_q in (Fraction(1, 2), Fraction(1), Fraction(2)):
                def _make_shift(col: str, aq: Fraction) -> Callable[[list[dict[str, float]], list[float]], Any]:
                    af = float(aq)
                    lbl = f"-({aq})" if aq.denominator != 1 else f"-{aq.numerator}"

                    def _fit(ds: list[dict[str, float]], ys: list[float]) -> Any:
                        b = _solve_linear([[1.0, r[col] ** (-af)] for r in ds], ys)
                        if b is None:
                            return None
                        c0, c1 = b
                        return (
                            f"{target} = {_fmt_num(c0)} + {_fmt_num(c1)} * {col}^{lbl}",
                            (lambda r, a=c0, m=c1, k=col, e=af: a + m * ((r[k] ** (-e)) if r[k] > 0.0 else float("nan"))),
                            {col: str(-aq)},
                            {"c0": _num(c0), "c1": _num(c1)},
                        )
                    return _fit

                evaluate_and_add("shifted_power", _make_shift(p_col, alpha_q), complexity_k=3, k_eff=2.5)

        if all(r[p_col] > 1.05 for r in train):
            def _make_invlog(col: str) -> Callable[[list[dict[str, float]], list[float]], Any]:
                def _fit(ds: list[dict[str, float]], ys: list[float]) -> Any:
                    b = _solve_linear([[1.0, 1.0 / math.log(r[col])] for r in ds], ys)
                    if b is None:
                        return None
                    c0, c1 = b
                    return (
                        f"{target} = {_fmt_num(c0)} + {_fmt_num(c1)} / ln({col})",
                        (lambda r, a=c0, m=c1, k=col: a + m / math.log(r[k]) if r[k] > 1.0 else float("nan")),
                        {},
                        {"c0": _num(c0), "c1": _num(c1)},
                    )
                return _fit

            evaluate_and_add("inverse_log", _make_invlog(p_col), complexity_k=2, k_eff=2.25)

        if pos_y:
            def _make_exp(col: str) -> Callable[[list[dict[str, float]], list[float]], Any]:
                def _fit(ds: list[dict[str, float]], ys: list[float]) -> Any:
                    b = _solve_linear([[1.0, r[col]] for r in ds], [math.log(y) for y in ys])
                    if b is None:
                        return None
                    c1 = b[1]
                    if any(abs(c1 * r[col]) > 50.0 for r in ds):
                        return None
                    zs = [math.exp(c1 * r[col]) for r in ds]
                    de = sum(z * z for z in zs)
                    if de <= 1e-30:
                        return None
                    c0 = sum(z * y for z, y in zip(zs, ys)) / de
                    return (
                        f"{target} = {_fmt_num(c0)} * exp({_fmt_num(c1)} * {col})",
                        (lambda r, a=c0, m=c1, k=col: a * math.exp(m * r[k]) if abs(m * r[k]) < 300.0 else float("inf")),
                        {},
                        {"c0": _num(c0), "c1": _num(c1)},
                    )
                return _fit

            evaluate_and_add("exponential", _make_exp(col=p_col), complexity_k=2, k_eff=2.25)

    # 4. Rational ratios y = (c0 + c1 * x_i) / (1 + c2 * x_j) (checked on ds only!)
    # DIS-15 (documented truncation): restricted to the first 3 predictors to bound the O(P^2) search.
    for p1 in free_predictors[:3]:
        for p2 in free_predictors[:3]:
            def _make_rat(ca: str, cb: str) -> Callable[[list[dict[str, float]], list[float]], Any]:
                def _fit(ds: list[dict[str, float]], ys: list[float]) -> Any:
                    b = _solve_linear([[1.0, r[ca], -y * r[cb]] for r, y in zip(ds, ys)], ys)
                    if b is None:
                        return None
                    c0, c1, c2 = b
                    # M5: reject the degenerate denominator (1 + 0*x) so a ~0 c2 never yields a
                    # nominally "rational" law that is really just a linear numerator.
                    if abs(c2) < 1e-12:
                        return None
                    if any(abs(1.0 + c2 * r[cb]) <= 0.15 for r in ds):
                        return None
                    return (
                        f"{target} = ({_fmt_num(c0)} + {_fmt_num(c1)} * {ca}) / (1 + {_fmt_num(c2)} * {cb})",
                        (lambda r, x0=c0, x1=c1, x2=c2, ka=ca, kb=cb: (x0 + x1 * r[ka]) / (1.0 + x2 * r[kb]) if abs(1.0 + x2 * r[kb]) > 1e-12 else float("inf")),
                        {},
                        {"c0": _num(c0), "c1": _num(c1), "c2": _num(c2)},
                    )
                return _fit

            evaluate_and_add("rational_ratio", _make_rat(p1, p2), complexity_k=3, k_eff=3.0)

    raw_non_null = [c for c in raw_candidates if c["family"] != "null_constant"]
    n_candidates_evaluated = len(raw_non_null)
    if n_candidates_evaluated <= 1:
        warnings_list.append(
            f"Only {n_candidates_evaluated} non-null candidate model was evaluated; multiplicity penalty is uninformative."
        )

    # Rank strictly using out-of-fold cross-validation BIC inside train — NEVER holdout (P-02)!
    # When --units is given, prefer dimensionally_consistent=True among tied/near-tied complexity models.
    seen_expr: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for c in sorted(
        raw_candidates,
        key=lambda item: (
            item["_val_bic"],
            0 if item.get("dimensionally_consistent") else 1,
            item["complexity_k"],
            item["train_bic"],
        ),
    ):
        if c["expr"] in seen_expr:
            continue
        seen_expr.add(c["expr"])
        deduped.append(c)

    non_null_ranked = [c for c in deduped if c["family"] != "null_constant"]
    # Multiplicity-adjusted threshold: Kass-Raftery 6.0 + 2 * ln(M_evaluated), evaluated ONLY on the #1 blind winner.
    # DIS-7: the BIC margin is applied to the out-of-fold `_val_bic` (the quantity the winner is
    # actually ranked on), not the in-sample `train_bic` (which is systematically lower/optimistic).
    bic_margin = 6.0 + 2.0 * math.log(max(1, n_candidates_evaluated))
    beats_null = False
    if non_null_ranked:
        winner = non_null_ranked[0]
        if (
            bool(winner.get("_holdout_valid", True))
            and (null_val_bic - float(winner["_val_bic"])) >= bic_margin
            and float(winner["val_rmse"]) < null_val_rmse
            and float(winner["holdout_rmse"]) < 0.95 * null_holdout_rmse
            and float(winner["holdout_r2"]) > 0.10
        ):
            beats_null = True

    ordered_final = (
        ([non_null_ranked[0]] + [c for c in deduped if c is not non_null_ranked[0]])
        if beats_null and non_null_ranked
        else deduped
    )

    top_pred_fn = ordered_final[0].get("_pred_fn")
    candidates: list[dict[str, Any]] = []
    for idx, c in enumerate(ordered_final[:8], start=1):
        clean_c = {k: v for k, v in c.items() if not k.startswith("_")}
        clean_c["id"] = f"C_LAW_{idx}"
        candidates.append(clean_c)

    top = candidates[0]
    # D1: a holdout RMSE at machine precision relative to the target scale means the model
    # memorized the data (circular discovery), not a real generalization.
    mean_abs_y = sum(abs(v) for v in y_all) / len(y_all)
    if float(top["holdout_rmse"]) / max(mean_abs_y, 1e-30) < 1e-10:
        warnings_list.append(
            f"Top candidate holdout RMSE ({top['holdout_rmse']:.3g}) is below 1e-10 of the target scale "
            f"(mean|y|={mean_abs_y:.3g}); this is a machine-precision fit and likely circular discovery."
        )
    max_sort = max(r[sort_col] for r in cleaned)
    next_regime = max_sort * 1.5 if max_sort > 0 else max_sort + 1.0
    falsifier_point: dict[str, float] = {
        p: float(statistics.median(r[p] for r in train)) for p in predictors
    }
    falsifier_point[sort_col] = float(next_regime)
    if falsifier_at:
        for fk, fv in falsifier_at.items():
            if fk not in predictors:
                raise ConjectureError(f"falsifier_at column {fk!r} is not in predictors {predictors!r}.")
            falsifier_point[fk] = float(fv)
    point_str = ", ".join(f"{p}={falsifier_point[p]:.4g}" for p in predictors)
    pred_note = ""
    falsifier_tol = float(top["holdout_rmse"]) * 3.0
    if callable(top_pred_fn):
        try:
            y_f = float(top_pred_fn(falsifier_point))
            if math.isfinite(y_f):
                pred_note = f"{target} ≈ {y_f:.6g} with "
                # N3: RELATIVE tolerance floor scaled by the predicted magnitude, never an absolute
                # 1e-4 (unit-dependent and physically meaningless).
                falsifier_tol = max(float(top["holdout_rmse"]) * 3.0, 1e-6 * abs(y_f))
                if abs(y_f) > 0.0 and falsifier_tol < 100.0 * math.ulp(abs(y_f)):
                    warnings_list.append(
                        f"Falsifier tolerance {falsifier_tol:.3g} is below ~100 ULP of the predicted value "
                        f"({y_f:.6g}); the tolerance is at machine precision."
                    )
        except (TypeError, ValueError, ZeroDivisionError, OverflowError):
            pred_note = ""
    falsifier = (
        f"At ({point_str}) (beyond observed {sort_col} max {max_sort:.4g}), "
        f"candidate {top['id']} ('{top['expr']}') must predict {pred_note}"
        f"max_abs_error <= {falsifier_tol:.4g}."
    )
    clean_source_ids = [str(s).strip() for s in (source_ids or []) if str(s).strip()]
    return {
        "target": target,
        "predictors": list(predictors),
        "units": dict(units) if units is not None else None,
        "source_ids": clean_source_ids,
        "likelihood_scale": "additive_gaussian_y",
        "n_candidates_evaluated": n_candidates_evaluated,
        "sort_by": sort_col,
        "holdout_mode": holdout_mode,
        "train_count": len(train),
        "holdout_count": len(holdout),
        "null_train_bic": _num(null_train_bic),
        "null_val_rmse": _num(null_val_rmse),
        "null_holdout_rmse": _num(null_holdout_rmse),
        "beats_null": beats_null,
        "warnings": warnings_list,
        "candidates": candidates,
        "pareto_frontier": _pareto_frontier_internal(candidates),
        "falsifier_point": falsifier_point,
        "falsifier_prediction": falsifier,
    }


def compute_conjectures_sha256(payload: dict[str, Any]) -> str:
    body = {k: v for k, v in payload.items() if k != "sha256"}
    canonical = json.dumps(body, sort_keys=True, allow_nan=False, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def seal_conjectures(
    report_dir: Path,
    payload: dict[str, Any],
    *,
    out_path: Path | None = None,
) -> Path:
    """Seal candidate conjectures to appendix/conjectures.json with strict JSON and SHA-256."""
    dest = out_path if out_path is not None else (Path(report_dir) / "appendix" / CONJECTURES_JSON)
    dest.parent.mkdir(parents=True, exist_ok=True)
    record: dict[str, Any] = dict(payload)
    record.setdefault("sealed_utc", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    record.pop("sha256", None)
    record["sha256"] = compute_conjectures_sha256(record)
    dest.write_text(json.dumps(record, indent=1, allow_nan=False, ensure_ascii=False) + "\n", encoding="utf-8")
    return dest


def _cmd_units(args: argparse.Namespace) -> int:
    variables: dict[str, str] = {}
    target: str | None = args.target
    if args.spec is not None:
        try:
            spec_data = json.loads(args.spec.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"Error: Invalid units spec {args.spec}: {exc}", file=sys.stderr)
            return 1
        if isinstance(spec_data, dict):
            raw_vars = spec_data.get("variables")
            if isinstance(raw_vars, dict):
                variables.update({str(k): str(v) for k, v in raw_vars.items()})
            elif all(isinstance(v, str) for v in spec_data.values()):
                variables.update({str(k): str(v) for k, v in spec_data.items()})
            if target is None and spec_data.get("target"):
                target = str(spec_data["target"])
    for item in args.var or []:
        if "=" not in item:
            print(f"Error: --var expects NAME=UNIT, got {item!r}.", file=sys.stderr)
            return 1
        k, v = item.split("=", 1)
        variables[k.strip()] = v.strip()

    try:
        groups = buckingham_pi(variables, target=target)
    except UnitError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    payload = {"variables": variables, "target": target, "groups": groups}
    if args.json:
        print(json.dumps(payload, indent=1, allow_nan=False, ensure_ascii=False))
    else:
        if not groups:
            print("No dimensionless groups exist for the supplied variables.")
        for g in groups:
            print(f"{g['name']}: {g['expr']}  exponents={g['exponents']}")
    return 0


def _cmd_discover(args: argparse.Namespace) -> int:
    import local_data  # noqa: PLC0415

    if not args.csv_path.is_file():
        print(f"Error: Data file not found: {args.csv_path}", file=sys.stderr)
        return 1
    try:
        table_rows = local_data.read_table(args.csv_path)
    except Exception as exc:  # noqa: BLE001
        print(f"Error: Unable to read {args.csv_path}: {exc}", file=sys.stderr)
        return 1

    predictors = [c.strip() for c in args.predictors.split(",") if c.strip()]
    units_map: dict[str, str] | None = None
    if args.units:
        units_map = {}
        for part in args.units.split(","):
            part = part.strip()
            if not part:
                continue
            if "=" not in part:
                print(f"Error: --units expects k=u pairs, got {part!r}.", file=sys.stderr)
                return 1
            uk, uv = part.split("=", 1)
            units_map[uk.strip()] = uv.strip()

    source_ids: list[str] = []
    if args.source_ids:
        source_ids = [s.strip() for s in args.source_ids.split(",") if s.strip()]
    falsifier_at: dict[str, float] | None = None
    if args.falsifier_at:
        falsifier_at = {}
        for part in args.falsifier_at.split(","):
            part = part.strip()
            if not part:
                continue
            if "=" not in part:
                print(f"Error: --falsifier-at expects col=float pairs, got {part!r}.", file=sys.stderr)
                return 1
            fk, fv = part.split("=", 1)
            try:
                val = float(fv.strip())
            except ValueError:
                print(f"Error: --falsifier-at expects numeric value for {fk.strip()!r}, got {fv!r}.", file=sys.stderr)
                return 1
            if not math.isfinite(val):
                print(f"Error: --falsifier-at value for {fk.strip()!r} must be finite (not nan/inf), got {fv!r}.", file=sys.stderr)
                return 1
            falsifier_at[fk.strip()] = val

    try:
        result = discover_laws(
            table_rows,
            target=args.target,
            predictors=predictors,
            units=units_map,
            holdout_mode=args.holdout_mode,
            holdout_fraction=args.holdout_fraction,
            sort_by=args.sort_by,
            snap_rationals=not args.no_snap,
            max_denom=args.max_denom,
            seed=args.seed,
            source_ids=source_ids,
            falsifier_at=falsifier_at,
        )
        # DIS-11: store data_file as a report-relative path (relative to cwd, the report_dir used
        # by seal_conjectures) instead of an absolute path, to avoid leaking local paths and to keep
        # the sealed artifact reproducible across machines.
        try:
            rel_data = os.path.relpath(args.csv_path, Path.cwd()).replace(os.sep, "/")
        except ValueError:
            rel_data = args.csv_path.name
        result["data_file"] = rel_data
        result["data_sha256"] = hashlib.sha256(args.csv_path.read_bytes()).hexdigest()
        sealed = seal_conjectures(Path.cwd(), result, out_path=args.out)
    except (ConjectureError, UnitError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    for w in result.get("warnings") or []:
        print(f"Warning: {w}", file=sys.stderr)
    if args.json:
        print(sealed.read_text(encoding="utf-8"), end="")
    else:
        top = result["candidates"][0]
        print(
            f"Sealed {len(result['candidates'])} candidate(s) to {sealed} "
            f"(evaluated={result['n_candidates_evaluated']}, train={result['train_count']}, holdout={result['holdout_count']}, "
            f"beats_null={result['beats_null']}, top: {top['id']} '{top['expr']}', holdout_rmse={top['holdout_rmse']})"
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description="Dimensional analysis (Buckingham Pi) and data-driven symbolic conjecture engine."
    )
    parser.add_argument("--version", action="version", version=f"conjecture.py {__version__}")
    sub = parser.add_subparsers(dest="subcommand", required=True)

    p_units = sub.add_parser("units", help="Compute exact rational Buckingham Pi dimensionless groups.")
    p_units.add_argument("--spec", type=Path, default=None, help="JSON file with {'variables': {...}, 'target': '...'}.")
    p_units.add_argument("--var", action="append", default=[], metavar="NAME=UNIT", help="Predictor variable unit.")
    p_units.add_argument("--target", default=None, metavar="NAME[=UNIT]", help="Target variable (isolated in pi_1).")
    p_units.add_argument("--json", action="store_true", help="Emit JSON output.")

    p_disc = sub.add_parser("discover", help="Discover candidate symbolic laws from a data table and seal conjectures.json.")
    p_disc.add_argument("csv_path", type=Path, help="Input CSV/TSV/XLSX/JSON table path.")
    p_disc.add_argument("--target", required=True, help="Target column name (or '__invariant__' for conservation scan).")
    p_disc.add_argument("--predictors", required=True, help="Comma-separated predictor column names.")
    p_disc.add_argument(
        "--units",
        default=None,
        help="Optional comma-separated NAME=UNIT definitions (adds Buckingham Pi candidates and tags dimensionally_consistent on all data-driven candidates).",
    )
    p_disc.add_argument(
        "--source-ids",
        default=None,
        help="Optional comma-separated sources.csv claim_ids from which csv_path was derived (e.g. C5,C6) so the validator excludes them from counting as replication data.",
    )
    p_disc.add_argument(
        "--falsifier-at",
        default=None,
        help="Optional comma-separated col=value predictor point for the out-of-domain falsifier prediction.",
    )
    p_disc.add_argument("--sort-by", default=None, help="Column used to order tail holdout split.")
    p_disc.add_argument("--holdout-mode", choices=("tail", "random"), default="tail", help="Holdout split strategy.")
    p_disc.add_argument("--holdout-fraction", type=float, default=0.25, help="Fraction of rows held out (0.1..0.5).")
    p_disc.add_argument("--max-denom", type=int, default=8, help="Maximum denominator when snapping rational exponents.")
    p_disc.add_argument("--no-snap", action="store_true", help="Disable rational exponent snapping.")
    p_disc.add_argument("--seed", type=int, default=0, help="Deterministic PRNG seed.")
    p_disc.add_argument("--out", type=Path, default=Path("appendix") / CONJECTURES_JSON, help="Output JSON path.")
    p_disc.add_argument("--json", action="store_true", help="Print sealed JSON to stdout.")

    args = parser.parse_args(argv)
    if args.subcommand == "units":
        return _cmd_units(args)
    if args.subcommand == "discover":
        return _cmd_discover(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
