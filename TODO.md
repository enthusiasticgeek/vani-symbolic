# vani-symbolic — TODO

> Compiler builtins that already exist and must NOT be reimplemented:
> `push` `len` `vec` `i64_to_str` `clone_at`
>
> No deps (self-contained).

---

## v0.1.0 — Implemented ✓

### Construction (12 functions)
- [x] `sym_arena_new`, `symtab_new` -- empty arena / symbol table
- [x] `sym_num` -- Num leaf (kind 0)
- [x] `sym_var` -- interns the name (see `symtab_intern`), pushes a Var
      leaf (kind 1) referencing the resulting `var_id`
- [x] `symtab_intern` -- dedups by name, assigns dense 0-based `var_id`s
      in first-seen order; bare `Vec<OwnedStr>` index reads are rejected
      by the checker (non-Copy element, would alias + double-free), so
      this uses the established `for x in ref xs` borrow pattern instead
- [x] `symtab_name_at` -- owned copy of a `var_id`'s display name, via
      the builtin `clone_at`
- [x] `sym_add`, `sym_sub`, `sym_mul`, `sym_div`, `sym_pow`, `sym_neg` --
      one builder per non-leaf kind; each bounds-checks its child
      index(es) inline (factoring into a shared helper hit a real
      checker limitation -- see `src/lib.vani`'s comment above `sym_add`)

### Introspection (2 functions)
- [x] `sym_kind`, `sym_is_leaf`

### Evaluation (1 function + 1 private helper)
- [x] `sym_eval` -- substitutes variables via a direct
      `var_values[var_id]` index read (zero string comparison anywhere
      in the eval path); `Pow` supports nonnegative integer exponents
      only, via `_sym_ipow` (exponentiation by squaring)

### Printing (1 function + 4 private helpers)
- [x] `sym_to_str` -- precedence-aware (Add/Sub=1, Mul/Div=2, Neg=3,
      Pow=4, atoms=5), Sub/Div left-associative, Pow right-associative,
      `Neg(Neg(x))` always parenthesized to avoid `--x`. A genuinely new
      pattern in this ecosystem -- `tests/test_print.vani` IS the spec
      for spacing/paren rules, since no external "correct answer" exists
      for this pattern the way hand-computed arithmetic values exist for
      every other package here.

### Structural equality (1 function)
- [x] `sym_eq_structural` -- same-SHAPE equality only, NOT
      semantic/commutative (`1+2` and `2+1` are NOT equal here);
      commutative canonicalization is a v0.2 (simplification tier)
      concern

### Tests
- [x] `tests/test_construction.vani` -- one case per builder, symtab
      dedup, a deeply nested 5-level chained build
      (`((((1+2)*3)-4)/5)^2`)
- [x] `tests/test_equality.vani` -- identical/same-shape-different-
      literal/commutatively-different-but-structurally-unequal cases,
      plus a deeply nested tree vs. an independently rebuilt equal copy
- [x] `tests/test_eval.vani` -- every op in isolation, `Pow` at
      exponents exercising multiple squaring iterations (`2^10=1024`),
      a deeply nested multi-variable case, a shared-subexpression-reuse
      case unique to the arena design
- [x] `tests/test_print.vani` -- every op alone plus the full
      precedence/associativity matrix, checked character-for-character
      on a deeply nested case

### Example
- [x] `examples/symbolic_demo.vani` -- `p(x) = 2x^3 - 3x^2 + x - 5`,
      demonstrating both the "reuse a node index" and "re-call
      `sym_var`" patterns side by side; evaluated at 4 points and
      printed, the composed construction+eval+print check this
      package's build order specifically calls for before considering
      a layer done

### Safety annotations
- [x] `#[bounded_stack(bytes=N)]` on every eligible function, set to
      `vanic audit-safety`'s exact reported number (never hand-derived
      -- got full clean coverage on the first pass here, unlike most
      prior packages in this ecosystem which needed 2+ convergence
      rounds)
- [x] `#[wcet(cycles=N)]` on every fixed-shape function; recursive
      functions (`sym_eval`, `sym_to_str`/`_sym_to_str_prec`,
      `sym_eq_structural`) are legitimately exempt from BOTH
      `#[bounded_stack]` and `#[wcet]` -- unbounded recursion depth
      (tree depth, a runtime value) makes both uncomputable, not just
      WCET
- [x] `vanic audit-safety` reports full clean coverage, no
      `--allow-partial-safety-coverage` escape hatch needed
- [x] Full `vanic check` (real SMT verification) passes clean on every
      test file and the example, on both backends

---

## v0.2.0 — Implemented ✓

Flagged in the roadmap as the highest-risk phase in the whole symbolic
tier -- a wrong rule silently poisons everything built on top of it.
Scoped deliberately narrow (see `src/lib.vani`'s design notes and the
v0.2.0 plan): like-term collection only covers flat linear combinations
of `Num`/`Var`/`Mul(Num,Var)` monomials, NOT general polynomial normal
form (no multiplicative factor combination, no cross-operator
associativity flattening).

### Simplification (1 function + 3 private helpers)
- [x] `sym_simplify(src, root, dst)` -- builds a simplified copy into a
      SEPARATE arena via the existing builder functions; never mutates
      `src` in place (the arena only ever grows, per v0.1.0's design
      note). Two layers:
  - **Layer 1** (`Mul`/`Div`/`Pow`/`Neg`): constant folding (`Num op
    Num -> Num`, via `_sym_fold_binary`, mirroring `sym_eval`'s exact
    trap semantics) and identities (`x*1`/`1*x`, `x*0`/`0*x`, `x/1`,
    `x^1`, `x^0` -- safe unconditionally even at `x=0`, matching
    `_sym_ipow`'s existing behavior -- and `Neg(Neg(x)) -> x`, correct
    for arbitrarily deep chains via how the recursion unwinds).
  - **Layer 2** (`Add`/`Sub`, via `_sym_flatten_sum` +
    `_sym_simplify_sum`): flattens a chain of nested `Add`/`Sub` into
    signed terms, simplifies each individually, classifies as constant/
    variable-monomial/opaque, collects like terms by `var_id` (sorted
    ascending for canonical output), and rebuilds. Constant folding
    through `Add`/`Sub` (`2+3->5`) falls out of this layer, not Layer 1.
- [x] Explicit, documented semantics policy: simplification assumes
      well-defined inputs. Since `sym_eval` is strict (both operands of
      a binary op are evaluated before combining), an identity like
      `0*x -> 0` changes *whether a trap occurs* if `x` itself would
      trap -- validation only compares behavior at points where the
      *original* expression evaluates successfully.

### Tests
- [x] `tests/test_simplify_folding.vani` -- exact-structure assertions
      per Layer 1 fold/identity, plus **property-based validation**
      (`seed_rng` + `rand_in_range`, 8 random sample points per
      expression, deterministic across runs) confirming
      `sym_eval(simplify(e)) == sym_eval(e)` -- the primary correctness
      gate per the v0.2.0 plan, not just hand-picked examples. A
      `rand_nonzero` resampling helper keeps sampled divisors from
      triggering the *original* expression's own division-by-zero trap.
- [x] `tests/test_simplify_collect.vani` -- the roadmap's own
      `2x+3x->5x` example, `x-x->0`, constant folding through `Add`/
      `Sub`, a mixed multi-term case (`2*x + y*y + 3 - x + 5`, combining
      collection with an opaque `y*y` term) verified both by property-
      based sampling and an exact spot-check, and a full-cancellation
      case (`2x+3x-x-4x -> 0`).
- [x] `examples/simplify_demo.vani` -- a deliberately messy expression
      exercising every identity and the collection logic together in
      one tree, simplifying to `6*x + -1*y + 3` (verified against a
      hand-derivation) -- the composed check this package's build order
      has required at the end of every phase so far.

### Safety annotations
- [x] `vanic audit-safety` reported exactly one missing attribute after
      this version's functions were added (`_sym_fold_binary`); every
      other new function is exempt from both `#[bounded_stack]` and
      `#[wcet]` (recursion depth is the tree depth or the number of
      flattened terms, a runtime value) -- confirmed to match the
      v0.2.0 plan's prediction before implementation started.
- [x] Full `vanic check` (real SMT verification) passes clean on every
      test file and both examples, on both backends, deterministic
      across repeated runs.

---

## v0.3.0 — Implemented ✓

### Differentiation (1 function)
- [x] `sym_diff(arena, root, var_id)` -- one rule per node kind, the
      full kind set (Num/Var/Add/Sub/Neg/Mul/Div/Pow): sum, difference,
      negation, product, quotient, and power (with chain rule via the
      power rule -- `Pow`'s only composition point, since `ExprNode` has
      no transcendental-function kinds yet). Appends new derivative-
      combinator nodes to the SAME arena `root` lives in (unlike
      `sym_simplify`'s separate-`dst` design) -- reuses existing node
      indices directly for any subexpression unchanged in the derivative
      (e.g. `v` in the product rule's `u'*v + u*v'`), safe because the
      arena only ever grows. `Pow`'s exponent must be a literal `Num`
      (variable/expression exponents need log-differentiation, out of
      scope); `n == 0` is a special case since `u^(n-1)` would need
      exponent `-1`. Raw output is deliberately NOT simplified --
      `sym_simplify` is a separate, composable pass, per the plan's
      "raw differentiation output needs the simplifier to stay
      readable" note.
- [x] Every local variable given a rule-specific name suffix
      (`_add`/`_sub`/`_neg`/`_mul`/`_div`/`_pow`), even across
      non-overlapping if-branches, to sidestep vāṇी's known LLVM
      codegen bug where reusing one local name across sibling branches
      of the same function can crash with "multiple definition of local
      value" even though the branches never execute together.

### Tests
- [x] `tests/test_diff.vani` -- exact-structure checks per rule
      (including directly asserting the arena-reuse property: a
      derivative subterm's index equals the ORIGINAL subexpression's
      index, not a copy), evaluation checks against hand-derived closed
      forms (a cubic polynomial, a multivariable product+power
      expression), a composed `sym_diff` + `sym_simplify` eval-preserving
      check, and **the plan's own required cross-package composed
      check**: `sym_diff`'s symbolic derivative (evaluated via
      `sym_eval` at integer sample points) cross-checked against
      vendored `vani-calculus`'s `diff_central` numeric derivative at
      the same points, for both a plain polynomial and a chain-rule
      case (`(x+1)^3`). All four run/build × backend combinations pass;
      full SMT `vanic check` clean.
- [x] `examples/diff_demo.vani` -- composed construction+diff+simplify+
      eval+print check on the same `p(x) = 2x^3-3x^2+x-5` that
      `symbolic_demo.vani` builds, demonstrating both why raw `sym_diff`
      output needs the `sym_simplify` pass (readability) and why the
      simplifier's own documented scope limit (no cross-operator
      associativity flattening) still leaves e.g. `2*3*x^2` unfolded to
      `6*x^2` -- not a bug, a known, already-documented boundary.

### Dependency
- [x] Vendored `vani-calculus` v0.3.0 via `vanic add calculus`, tests/
      examples-only (production `sym_diff` has zero `calculus::` calls)
      -- matches this ecosystem's established pattern of vendoring a
      package purely to enable a cross-check test (e.g. vani-sparse
      vendors vani-matrix the same way, for the same reason).

### Safety annotations
- [x] `sym_diff` is exempt from both `#[bounded_stack]` and `#[wcet]`
      (recursion depth is the tree depth, a runtime value) -- confirmed
      via `vanic audit-safety`: full clean coverage, no gap introduced.
- [x] Full `vanic check` (real SMT verification) passes clean on every
      test file and both examples, on both backends.

---

## Future

Phased breakdown (versions proposed, not committed) tracked in
[kosh-index/ROADMAP.md](https://github.com/enthusiasticgeek/kosh-index/blob/main/ROADMAP.md)'s
`vani-symbolic` scoping section. Each phase needs its own
confirm-before-starting, same discipline as this package itself.

- **v0.4.0: Basic symbolic integration** -- a fixed pattern table
  (term-by-term polynomial power rule, elementary antiderivatives, a
  few recognized `u`-substitution shapes), not a general algorithm (no
  Risch). Not started.
- **v0.5.0: Simple equation solving** -- linear directly, quadratic via
  `vani-algebra`'s existing closed-form solver. Not started.
- **v0.6.0+: Polynomial factorization** -- folds in what would have
  been a separate `vani-polyalgebra` repo (rational-root theorem +
  synthetic division). Gröbner bases stay out of scope unless a real
  use case shows up. Not started.
- **`BigInt`-backed `Num` values** -- a `Vec<BigInt>` side table
  (parallel to `SymbolTable.names`), reinterpreting `Num.value` as an
  index rather than a literal. No `ExprNode` shape change needed when
  this lands. Not started, not scheduled to a specific version yet.
