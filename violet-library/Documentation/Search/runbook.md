# Search index runbook

## What runs where

GitHub stores the code and runs the full index build in Actions. The pinned book file and finished search artifacts live in `Tox1/LibrariesBookData` on Hugging Face. The full build command refuses to run outside GitHub Actions so a teammate cannot accidentally download the real catalog onto a laptop. Tests use synthetic books only.

## Check code without the dataset

1. Create a project-only Python 3.11 environment: `python -m venv .venv`.
2. Install test tools: `python -m pip install -e '.[dev]'`.
3. Run `ruff check .` and `python -m pytest -q`.

The project environment and caches are ignored by Git. This step does not download the model, the real book file, or the indexes.

## Build and publish in the cloud

1. Check the pinned `SOURCE_REVISION` and `MODEL_REVISION` in `src/libraries_search/config.py`. The source revision must contain the expected `manifest.json` and `data/books.parquet`.
2. Confirm the GitHub Actions repository secret `HF_TOKEN` can write to `Tox1/LibrariesBookData`.
3. Open **Actions → Build and publish owned search index → Run workflow** on `main`. The same workflow also runs when search code or its workflow reaches `main`.
4. Follow four parallel shard jobs, then the assemble, smoke-search, and publish job. Each shard checks the pinned source and its own vectors. Assembly rejects missing or changed shards, checks all row ranges and revisions, and verifies source and output checksums, schema, counts, vector dimensions, SQLite integrity, and row alignment before upload.
5. Verify the current versioned `search/v2/manifest.json`, `search/v2/books.sqlite`, and `search/v2/vectors.npy` in the Hugging Face dataset. Compare the published manifest with the Actions log.

The first successful full build is [GitHub Actions run 43682889772](https://github.com/VeedantBrahmbhatt/Libraries/actions/runs/43682889772); its [Hugging Face commit](https://huggingface.co/datasets/Tox1/LibrariesBookData/commit/f54ded49b97a92ca8e5dce0463500043ea2a19a4) contains the three files. The [manifest at that commit](https://huggingface.co/datasets/Tox1/LibrariesBookData/raw/f54ded49b97a92ca8e5dce0463500043ea2a19a4/search/v1/manifest.json) records 91,667 books, 384 dimensions, both input revisions, checksums, and file sizes. The SQLite index is 367,140,864 bytes and the vector file is 140,800,640 bytes. The run took about 56 minutes; future runs can vary with runner load and book text length.

The workflow installs a CPU-only model runtime. Four jobs each encode about one quarter of the books; their vector files are held as GitHub Actions artifacts for one day only. The assembly job joins the vectors in source order and builds the keyword index. All jobs use temporary runner disk and delete their source cache and output directories after every run. `HF_TOKEN` is available only in the publishing step. No index is committed to GitHub.

The later [metadata-only v2 upgrade](https://github.com/VeedantBrahmbhatt/Libraries/actions/runs/43781216697) reused the checked v1 vectors and rebuilt only book metadata. It added alternate-title keyword matching and used the source's alternate-language abstract when the primary abstract was empty. The [v2 snapshot](https://huggingface.co/datasets/Tox1/LibrariesBookData/tree/b745902168aca10589fd0b376b58eb8019291b37/search/v2) contains 91,667 books; its vector checksum exactly matches v1. Use [the query-fit runbook](../Evaluation/query-fit-runbook.md) for the upgrade and its separate evaluation. The old v1 snapshot remains for comparisons.

## Reading the search output

The index is a set of files, not a hosted search service. For an interactive search, run the code on a remote machine with the model and index files available there. The project does not currently provide a live UI or shared query server. The GitHub Actions smoke check is the reproducible cloud example.

On a remote machine only, install `.[search]`, then fetch just the three published index files into a temporary directory:

```bash
export HF_HOME=/tmp/libraries-hf-cache
python - <<'PY'
from huggingface_hub import snapshot_download

snapshot_download(
    repo_id="Tox1/LibrariesBookData",
    repo_type="dataset",
    revision="b745902168aca10589fd0b376b58eb8019291b37",
    allow_patterns=["search/v2/*"],
    local_dir="/tmp/libraries-search",
)
PY
libraries-search --input-dir /tmp/libraries-search/search/v2 --query 'climate adaptation' --mode hybrid --limit 10
```

Delete those temporary directories when the remote session ends. Do not run these commands on a laptop under the current data-location rule. Baseline modes are `keyword`, `semantic`, and `hybrid`; `--offset` selects later results. The optional `reranked` mode loads another pinned model and is experimental because its current warm latency and relevance are not acceptable for a UI default. `rank_score` is a relative sorting value, not a probability or confidence percentage. V2 also returns a bounded source-description excerpt and identifies which source description field supplied it.

The workflow's smoke search proves that the published code can return results from the built index. It does not prove that students will find the results relevant; the [evaluation notes](../Evaluation/README.md) describe that separate requirement.

## Failure handling

| Signal | Response |
| --- | --- |
| Pinned source file or checksum changed | Stop. Compare the source revision and manifest before updating the pin. |
| Model returns wrong dimensions, missing values, or non-unit vectors | Stop. Check the pinned model revision and encoding instructions. |
| SQLite count or integrity fails | Stop. Do not upload a partial or misaligned index. |
| GitHub runner runs out of time or space | Inspect the completed log, adjust the build while keeping the same pinned inputs, and start a new workflow run. The temporary runner has no saved partial index, so a new run starts from the first book. Do not silently switch to an external search provider. |
| Hugging Face 401/403 | Check the `HF_TOKEN` secret permissions without printing the token. |
| Upload fails | Keep the previous index snapshot; rerun after fixing the cause. |

## Refreshing inputs

When the prepared book dataset changes, review its quality report, update the pinned source revision in code and documentation, then run the workflow again. When the meaning model changes, update its exact revision and rebuild every book vector. The versioned manifest records source and model revisions and file checksums so the team can trace any search result to its inputs. A metadata-only change can use the checked upgrade workflow when its source and v1 vector pins still apply.
