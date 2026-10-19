# Frozen new questions and repeated QA v7

40 newly authored questions on the existing 34-document CPython v3.12.7/project-guide corpus: 24 answerable and 16 unanswerable (eight missing facts, eight partially supported multi-part questions). Source anchors are validated. There is no exact question-text overlap with the previous 71 questions. These are author-labeled questions on a known corpus, not an independent external human-labeled benchmark or a new unseen corpus.

Eight fixed questions run three times, with the remaining 32 run once, for 56 planned trials. The bundle uses the existing grounded-answer evaluator in three separate output directories: primary-40, repeat-2 and repeat-3. Model-response caches are not copied between runs. Only embedding vectors are reused after checking provider/model identity and every corpus-file hash. The approved local continuation profile needs at most four new embedding requests and 224 chat requests; SDK automatic retries remain zero. Each child has its own persisted request cap, and the sum of the frozen child caps bounds the bundle. Do not create extra run directories or reset ledgers to retry failures.

```powershell
python scripts/evaluate_frozen_bundle.py --bundle-dir work/frozen-v7 --seed-vectors PATH_TO_PRIOR_VECTORS_JSON --seed-scope PATH_TO_PRIOR_SCOPE_JSON --prepare-scope work/frozen-v7-scope.json
# Review the frozen questions, sources, model and budget first.
python scripts/evaluate_frozen_bundle.py --bundle-dir work/frozen-v7 --scope-manifest work/frozen-v7-scope.json --allow-live-calls
```

This continuation runner assumes a prior matching vector cache, which is intentionally excluded from the public repository and patch archive. A new environment must first generate a fresh scope and vector cache with scripts/evaluate_answer_pipeline.py; the four-request continuation limit must not be claimed for a full uncached rebuild.

Labels, anchors and answer-pattern checks are kept local and never sent to the model. Completion/refusal contracts and lexical pattern checks are not independent factual accuracy. Review emitted answers and citations separately using the generated manual-review.csv files. Record the first frozen-set results before changing prompts or grading; subsequent fixes are regression work and cannot be presented as the original untouched holdout. Preserve the previous 71-question results.

## First frozen real run (2026-10-19)

All 56 trials were recorded: the first run completed 19/24 answerable questions and validly refused 16/16 unanswerable questions. Seven of eight selected questions met the contract in all three runs. Requests: 138 chat and four embeddings, including two BadRequestError attempts at question 21. That service failure was retained; a separate scheduling-only continuation completed remaining approved questions with unchanged frozen sources, prompts, grading, outputs and budgets.

Assistant semantic review found one accepted first-run answer (v7-new-18) conflating Task.eager_start with eager_task_factory; conservatively 18/24 first-run answerable questions passed this assistant review. This is not independent human accuracy. Across all trials, 28/34 answerable attempts completed, 27 passed assistant semantic review, and 22/22 unanswerable attempts were valid refusals. Three positive first-run questions were blocked by invalid/service responses; two were refused despite answerable labels. Five failed first-run IDs: 15, 16, 19, 21, 22. Logger.exception also showed malformed draft JSON on its third trial.

Follow-up should improve API-specific retrieval, quote context/antecedents and semantic scope checks, and clarify concurrent.futures.Future in future question versions. Do not weaken exact provenance checks or overwrite original scores. Current local Windows regression: 453 passed; new changes are not yet published and have no new Ubuntu CI.
