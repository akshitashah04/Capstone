# Fifty-persona evaluation plan

1. Write and freeze 50 fictional profiles and their queries before seeing search results. Validate count, ID uniqueness, level balance, language, and exact export to the standard query file.
2. Add a focused GitHub Actions job that collects keyword, semantic, and hybrid top-10 results from the pinned index on a temporary runner and uploads only the small result files.
3. Review the union of top-five books for each persona. Save separate assistant grades and evidence notes without changing the human-review sheets.
4. Score Success@5, top-one fit, pooled nDCG@5, and warm latency; show every persona's best result and compare undergraduate, graduate, and language groups.
5. Inspect weak cases, judge the strongest current search mode, update the root README and evaluation handover, run tests and checks, and publish the purpose branch to `main`.
