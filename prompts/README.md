# prompts/ — every prompt the benchmark sends, as data

| | |
| --- | --- |
| `v2.tsv` | The benchmark items: one forced comparison per row, entities in `[brackets]`. |
| `graders/<id>.md` | The text sent to the LLM judge for grader `<id>` — the current q-series (`q1_1`, `q1_2`, `q2`, `q3`, `q4`, `q4_1`–`q4_4`). |
| `graders/legacy/<id>.md` | The earlier generation (`preference1`, `preference2`, `relativism`, `whimsical`, `factual_depth`, and the superseded `q1`), kept because the database holds their grades. Legacy `justification` shares `q4.md`. |

`src/aestheticbench/benchmark/prompts.py` is the only reader of `graders/`.
The *scale* each grader scores on (allowed values, column name, generation)
is not here — it is `src/aestheticbench/benchmark/rubric.py`, and
`tests/test_question_specs.py` keeps the two in step. Every grader prompt is
wrapped in a JSON output instruction at send time; see
`Grader.construct_prompt` in `benchmark/grading.py`.

Changing a file here changes what the judge is asked. `AestheticBenchDB.get_grader_version()`
records the git hash of the last commit touching this directory alongside each grade.
