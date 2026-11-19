## Expert review

The production evaluation scored real conversations, and the judge failed the ones added to `datasets/golden.jsonl` in this PR (`"status": "needs_review"`).

For each new row, open the file in the browser (**Files changed → ⋯ → Edit file**) and fill in:

| Field | What to write |
|---|---|
| `human_verdict` | `pass` if the agent's answer was actually fine, `fail` if it was wrong |
| `ground_truth` | What a correct answer should do or say |
| `status` | Change `needs_review` to `approved` |

Remove a row if it isn't a useful test (for example, it contains personal data).

When you merge:

- every real failure becomes a permanent regression test that the release gate runs on each change;
- `human_verdict` vs `judge_verdict` tells us whether the judge scores correctly (`python scripts/feedback.py calibrate`).

Checks start after your first edit. The `validate` check stays red until every row has been reviewed, and then the golden gate runs the new cases against the dev agent.
