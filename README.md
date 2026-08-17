# vani-symbolic

Symbolic-math (CAS) foundation for the [vāṇी compiler](https://github.com/enthusiasticgeek/vani-compiler).
Implements the full planned symbolic tier in
[kosh-index/ROADMAP.md](https://github.com/enthusiasticgeek/kosh-index/blob/main/ROADMAP.md)
-- expression construction, numeric evaluation, precedence-aware
printing, simplification (constant folding, identities, like-term
collection), symbolic differentiation, degree<=2 equation solving,
polynomial integration (power rule, linearity, linear
u-substitution), and rational-root factorization (folded in from what
would have been a separate `vani-polyalgebra` repo, per the roadmap's
own decision). Gröbner bases, factorization over anything but the
rationals, and a general polynomial normal form stay out of scope --
see "What this library does NOT provide" below.

`ExprNode` is a plain `Copy` struct (four `i64` fields, no heap-owning
field) living in a flat `Vec<ExprNode>` arena, unlike the owned-`Vec`
sibling library ([vani-bignum](https://github.com/enthusiasticgeek/vani-bignum)).
Closer in shape to the Copy-struct libraries
([vani-complex](https://github.com/enthusiasticgeek/vani-complex),
[vani-interval](https://github.com/enthusiasticgeek/vani-interval)),
but a genuinely new pattern in this ecosystem: no existing package uses
a kind-tag-discriminated arena. Chosen because a recursive
`enum Expr { Add(Box<Expr>, Box<Expr>), ... }` does not compile in
vāṇी today -- see "Encoding" below.

**API reference / tutorial:** <https://enthusiasticgeek.github.io/vani-symbolic/>

## Add to your project

```toml
# vani.toml
[deps]
symbolic = { registry = "kosh", version = "^0.7" }
```

```sh
vanic add symbolic
vanic build
```

## What's included (v0.1.0-v0.7.0 — construction through rational-root factorization; see TODO.md)

| Module | Functions |
|---|---|
| Construction | `sym_arena_new`, `symtab_new`, `sym_num`, `sym_var`, `symtab_intern`, `symtab_name_at`, `sym_add`, `sym_sub`, `sym_mul`, `sym_div`, `sym_pow`, `sym_neg` |
| Introspection | `sym_kind`, `sym_is_leaf` |
| Evaluation | `sym_eval` (nonnegative-integer `Pow` exponents only) |
| Printing | `sym_to_str` (precedence-aware, matches SymPy's `str()` spacing convention) |
| Equality | `sym_eq_structural` (same-shape only, NOT commutative -- `1+2` and `2+1` are not equal here) |
| Simplification | `sym_simplify` (constant folding, identities, and like-term collection for flat linear combinations of monomials -- see "Simplification scope" below; NOT general polynomial normal form) |
| Differentiation | `sym_diff` (sum/difference/negation/product/quotient/power+chain rules -- see "Differentiation" below) |
| Equation solving, degree<=2 | `sym_poly_coeffs_le2`, `sym_solve_poly_le2` (delegates to `vani-algebra`'s real-root solver), `sym_solve_equation_le2` (two-sided `lhs = rhs` form, works even across different arenas) |
| Integration | `sym_integrate` -- power rule, linearity (`Add`/`Sub`/`Neg`), constant-multiple/-divisor rules, and recognized linear `u`-substitution shapes (`(ax+b)^n`); explicit `ok=false` for anything unrecognized (`1/x`, non-literal exponents, a product of two var-dependent factors, ...), never a guess |
| Rational-root factorization | `poly_rational_roots` (exact, via the rational-root theorem + exact-integer verification), `poly_factor_rational` (synthetic division via `vani-algebra`'s deflation step, roots with multiplicity), `sym_poly_coeffs` (arbitrary-degree generalization of `sym_poly_coeffs_le2`), `sym_factor_rational` (symbolic-tree entry point) |

## Encoding

```
struct ExprNode { kind: i64, value: i64, left: i64, right: i64 }
struct SymbolTable { names: Vec<OwnedStr> }
```

`kind`: `0`=Num `1`=Var `2`=Add `3`=Sub `4`=Mul `5`=Div `6`=Pow `7`=Neg.
Children are `i64` indices into the same arena (`-1` = none) instead of
pointers -- the flat-`Vec`-plus-explicit-index convention already used
by [vani-tensor](https://github.com/enthusiasticgeek/vani-tensor)'s
shape encoding and [vani-sparse](https://github.com/enthusiasticgeek/vani-sparse)'s
COO/CSR, applied to a tree instead of a matrix.

**Why not a recursive enum?** vāṇी's enum variants admit only a single
payload field in v1, and `box()` rejects a type that transitively
contains itself -- both confirmed by direct compiler test while scoping
this package. A naive `Add(Box<Expr>, Box<Expr>)` variant hits both
restrictions independently. See vani-compiler's
[`docs/missing_features.md`](https://github.com/enthusiasticgeek/vani-compiler/blob/main/docs/missing_features.md)
("Recursive / self-referential types") for the full writeup. The arena
representation sidesteps this entirely -- `ExprNode` is Copy, so no
function ever needs `ref`/`mut ref` on an individual node, only on the
whole `Vec<ExprNode>`.

`value`'s meaning depends on `kind`: `Num`'s literal, or `Var`'s dense
0-based `var_id` (an index into `SymbolTable.names`, assigned by
`symtab_intern` in first-seen order). Both fit one `i64` slot and never
coexist on the same node, so the field is reused rather than adding a
second field that would sit unused on every non-leaf node. This is
what lets `sym_eval` substitute variables via a direct
`var_values[var_id]` index read, with zero string comparison anywhere
in the evaluation path.

`Neg` is unary: uses `left` for its one child, `right` stays `-1` --
arity is a pure function of `kind`, never stored per-node.

## Simplification scope

`sym_simplify(src, root, dst)` builds a simplified copy into a
*separate* arena (never mutates `src` in place -- the arena only ever
grows). Two layers:

- **Constant folding + identities** for `Mul`/`Div`/`Pow`/`Neg`:
  `Num op Num -> Num`, `x*1`/`1*x` -> `x`, `x*0`/`0*x` -> `0`, `x/1` ->
  `x`, `x^1` -> `x`, `x^0` -> `1` (safe even at `x=0`), `Neg(Neg(x))`
  -> `x`.
- **Like-term collection** for `Add`/`Sub`, flattened across a chain of
  nested `Add`/`Sub` nodes: collects `Num`, bare `Var`, and
  `Mul(Num,Var)`/`Mul(Var,Num)` single-variable monomial terms by
  `var_id` (`2x + 3x -> 5x`), folds constants through the same chain
  (`2+3 -> 5`), and cancels to zero when terms fully cancel (`x-x ->
  0`). Anything else in the chain (a product of two variables, a `Pow`,
  a nested non-monomial `Mul`, ...) is kept as an opaque, unmerged term.

**This is deliberately not general polynomial normal form** --
multiplicative factor combination (`2*(3*x) -> 6*x`), `Mul`-chain
flattening, and canonicalizing anything beyond the specific `Add`/`Sub`
monomial case above are out of scope. Simplification also assumes
well-defined inputs: since `sym_eval` is strict (both operands of a
binary op are evaluated before combining), an identity like `0*x -> 0`
changes *whether a trap occurs* if `x` itself would trap when
evaluated -- correctness is validated at points where the *original*
expression evaluates successfully, matching this ecosystem's existing
assert-on-out-of-scope-input convention.

## Differentiation

`sym_diff(arena, root, var_id)` differentiates the subtree rooted at
`root` with respect to `var_id`, appending new derivative-combinator
nodes to the **same** arena `root` already lives in -- unlike
`sym_simplify`'s separate-`dst` design, differentiation reuses existing
node indices directly for any subexpression that appears unchanged in
the derivative (e.g. `v` in the product rule's `u'*v + u*v'`), since the
arena only ever grows and a node index stays valid forever once
returned.

One rule per node kind, covering the full kind set:

| Kind | Rule |
|---|---|
| `Num` | `-> 0` |
| `Var` | `-> 1` if this is `var_id`, else `-> 0` |
| `Add(u,v)` | `-> u' + v'` |
| `Sub(u,v)` | `-> u' - v'` |
| `Neg(u)` | `-> -u'` |
| `Mul(u,v)` | `-> u'*v + u*v'` (product rule) |
| `Div(u,v)` | `-> (u'*v - u*v') / (v*v)` (quotient rule) |
| `Pow(u,n)` | `-> n * u^(n-1) * u'` (power rule + chain rule) |

`Pow`'s exponent `n` must be a literal `Num` -- a variable/expression
exponent needs log-differentiation, out of scope (an extension of
`sym_eval`'s existing "nonnegative integer exponent only" restriction).
`n == 0` is a special case (`u^(n-1)` would need exponent `-1`, which
`sym_pow` doesn't support) -- handled directly since `d(u^0)/dx =
d(1)/dx = 0`.

**Raw output is deliberately not simplified** -- `sym_diff` and
`sym_simplify` are separate, composable passes; call `sym_simplify` on
the result to fold `1*x`, `x+0`, `x^1`, etc. into something readable
(see `examples/diff_demo.vani`). Note the current simplifier's
documented scope limits (no cross-operator associativity flattening)
mean a term like `2*(3*x^2)` from the chain rule stays as-is rather than
folding to `6*x^2` -- see "Simplification scope" above.

Validated in `tests/test_diff.vani` both by exact-structure checks per
rule (including confirming the arena-reuse property directly) and a
genuine cross-package check against vendored
[vani-calculus](https://github.com/enthusiasticgeek/vani-calculus)'s
`diff_central`: `sym_diff`'s symbolic derivative, evaluated at a point,
compared against the numeric central-difference derivative at the same
point. `vani-calculus` is vendored for this test/example validation
only -- production `sym_diff` makes zero calls into it.

## What this library does NOT provide

- **Transcendental functions** (`exp`/`ln`/`sin`/`cos`, ...). `ExprNode`'s
  kind set has never grown past the 8 kinds v0.1.0 shipped with --
  adding these would mean extending every existing walker (`sym_eval`,
  `sym_diff`, `sym_simplify`, `sym_to_str`, `sym_eq_structural`), a much
  larger undertaking than any single phase so far. `sym_integrate`
  covers polynomial integration only for this reason.
- **Integration/factorization beyond what's listed above.** `1/x ->
  ln|x|`, integration by parts, partial fractions, the Risch algorithm,
  Gröbner bases, and factorization over anything but the rationals are
  all explicitly out of scope, matching the roadmap's own "not a
  general algorithm" framing.
- **General polynomial normal form.** See "Simplification scope" above.
- **`BigInt`-backed numbers.** `Num.value` is a plain `i64`, matching
  this ecosystem's narrow-then-widen precedent. The design leaves room
  for a future `Vec<BigInt>` side table (parallel to
  `SymbolTable.names`) reinterpreting `Num.value` as an index rather
  than a literal, with no `ExprNode` shape change needed -- not built
  now (YAGNI until a real overflow problem shows up).
- **Commutative/semantic equality.** `sym_eq_structural` is same-shape
  only; canonicalizing `1+2` and `2+1` to compare equal is a
  simplification-tier concern.
- **Rational or negative `Pow` exponents.** `sym_eval` asserts the
  exponent is nonnegative and traps otherwise, matching this
  ecosystem's assert-on-out-of-scope-input convention.
- Compiler builtins that already exist and must NOT be reimplemented
  here: `push` `len` `vec` `i64_to_str` `clone_at`

## License

MIT
