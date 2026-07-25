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

## Future

Phased breakdown (versions proposed, not committed) tracked in
[kosh-index/ROADMAP.md](https://github.com/enthusiasticgeek/kosh-index/blob/main/ROADMAP.md)'s
`vani-symbolic` scoping section. Each phase needs its own
confirm-before-starting, same discipline as this package itself.

- **v0.2.0: Simplification** -- constant folding, identities (`x+0`,
  `x*1`, `x*0`, `x-x`), canonical ordering of commutative `Add`/`Mul`
  operands, like-term collection. Flagged as the highest-risk phase in
  the whole symbolic tier -- a wrong rule silently poisons everything
  built on top of it. Not started.
- **v0.3.0: Symbolic differentiation** (`sym_diff`) -- sum/product/
  quotient/chain/power rules. Validated against `vani-calculus`'s
  `diff_central` at sample points. Not started.
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
