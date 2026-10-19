# API scope and execution reliability

This change addresses observed first-run failures. The original frozen scores remain unchanged: CareerPilot first-run 19/24 answerable completions, 16/16 valid negative refusals; one accepted answer failed assistant semantic review. Model self-audit agreement is not independent factual accuracy.

- Source chunks now retain source-derived API declarations and paragraph context without changing their text or embedding identity. Exact API matching is preferred over conflicting methods, and neighbor windows stop at different known API scopes.
- Verified answer material carries the cited paragraph and declaration. A bounded deterministic rule rejects Boolean/null assignment claims that rename a target absent from that cited context. The actual cached eager-task failure is rejected before model audit. This narrow rule does not prove arbitrary semantic entailment.
- Invalid draft JSON, invalid schema, untraceable claims and assignment scope errors are distinguished. Provider diagnostics retain safe error class/status/code without exception bodies. No automatic repair or extra model retry was introduced.

A separate post-run diagnostic uses required factual source spans for the existing 24 positive questions. Five earlier labels spanned examples or unrelated APIs; the new diagnostic narrows those labels and does not replace the frozen evaluation. On the same cached vectors, required facts were retrieved for 21/24 questions before and 24/24 after. It is a known-data retrieval regression, not a new answer-quality result.

```powershell
python scripts/evaluate_api_scope.py --vectors PATH_TO_EXISTING_VECTORS_JSON --vector-scope PATH_TO_ITS_SCOPE_JSON --output work/api-scope-report.json
```

The script validates corpus fingerprints, finite vector dimensions and required spans, and prohibits network. No vector cache or credentials are committed. The old frozen scopes intentionally reject the changed source; a new live retest requires a newly reviewed scope.

Local Windows regression: 464 tests pass. The current changes have not had a new paid model retest. Capability claims, resume facts and historical results are unchanged.
