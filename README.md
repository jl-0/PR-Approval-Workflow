# Manager sign-off workflow

A working demonstration of a GitHub setup where **a nominated manager must sign
off on changes before they can merge — once a week, for everything at once,
without reading any code.**

The Python in this repository is synthetic filler, there only to give the
workflow something real to report on. The subject is `.github/workflows/`.

- **Live report page:** https://jl-0.github.io/PR-Approval-Workflow/
- **Detailed reference:** [docs/signoff-process.md](docs/signoff-process.md)

## The problem this solves

Someone outside the commit path — a manager, a QA lead, an external assessor —
has to accept what ships. They are not reviewing diffs. Requiring them to
approve every pull request makes them a per-change bottleneck and buries them in
email; asking them to approve nothing at all leaves no auditable record.

What you want is: changes pile up, and once a cycle that person reads one page
and presses one button.

## How it works

```
PR opened ──► "Queue for sign-off" posts a PENDING manager-signoff status
              ├─ branch rule requires that status, so the merge is blocked
              └─ no environment, no gate, NOBODY NOTIFIED

   ...pull requests accumulate through the week...

Monday 14:00 UTC, or Actions → Run workflow ──► "Batch sign-off"
   collect ──────► publish ──────► signoff
   (one report     (GitHub        (PAUSED — waiting on the reviewer)
    for every       Pages)              │
    queued PR)                          │  ONE approval
                                        ▼
                    flips manager-signoff to SUCCESS on every
                    reviewed PR → they all become mergeable
```

### What actually holds a pull request

GitHub calls the gate a *deployment*, but nothing is deployed. A "deployment" is
just a job that names an **environment**, and an environment can require named
reviewers before any job referencing it may start.

That gate alone cannot block a pull request, because a deployment belongs to the
commit the workflow ran on. So the gate's job is to write a **commit status**
called `manager-signoff` onto each reviewed pull request, and a branch rule
requires that status. One approval, many pull requests released.

`pr-queue.yml` posts that status as **pending** the moment a pull request opens.
A pending status blocks the merge and gives the author a readable reason —
*"Queued for the next sign-off batch"* — instead of an unexplained grey button.

### Why the reports are built in separate jobs

An environment gate pauses a job **before its first step runs**. If the report
were generated inside the gated job, the reviewer would have to approve it
before they could read it. Hence `collect` → `publish` → `signoff`.

## The moving parts

| Piece | What it does |
| --- | --- |
| `.github/workflows/pr-queue.yml` | On every PR, posts a pending `manager-signoff` status. Silent. |
| `.github/workflows/batch-signoff.yml` | Weekly or manual. Builds one report, publishes it, gates on approval, releases every PR. |
| `.github/workflows/ci.yml` | Ordinary unit tests. |
| `scripts/collect_prs.py` | Queries the GraphQL API for PRs, their labels, and the labels of every issue they close. |
| `scripts/render_report.py` | Renders that data as Markdown (run summary) and HTML (Pages) from one source. |
| Environment `external-signoff` | Holds the required-reviewer list. This is the gate. |
| Ruleset *Require manager sign-off on main* | Requires `Unit tests` + `manager-signoff`. This is the block. |

## What the reviewer sees

One notification per cycle: *"Deployment review required."* It links to the
workflow run, where they find:

1. **The report**, rendered on the page directly above the paused job — every
   pull request waiting, the work items each closes, and every tag involved.
2. **A link to the same report as a web page**, if they prefer that to the
   Actions UI.
3. **A "Review deployments" button.** They tick `external-signoff`, optionally
   leave a comment, and press *Approve and deploy* or *Reject*.

Approving releases every pull request in that report. Rejecting releases
nothing, and the same set reappears next cycle. The decision, the comment, the
identity and the timestamp are all recorded against the run.

A required reviewer needs **read access only** — they can never push, merge, or
change a workflow. On a public repository this protection rule is available on
every plan tier. (On a *private* repo it is GitHub Enterprise only, which
matters if you move this internally.)

### The report

Every report opens with a plain-English summary derived from the pull request
data — how much is waiting, what needs a closer look, what the batch consists
of, and which pull requests close no tracked work item. That last point is the
traceability question an assessor asks, so it is stated rather than left to be
noticed.

No model is involved and it costs nothing. GitHub Models — the free inference
endpoint — was retired on 30 July 2026. A Copilot-written summary can be
switched on by adding a `COPILOT_PAT` secret; without it those steps skip
entirely.

## Setting this up on your own repository

```bash
REPO=owner/name

# 1. The gate: an environment whose required reviewers are your approvers.
gh api -X PUT "repos/$REPO/environments/external-signoff" --input - <<'JSON'
{ "wait_timer": 0, "prevent_self_review": false,
  "reviewers": [{ "type": "User", "id": 0 }],
  "deployment_branch_policy": null }
JSON
# Replace id 0 with the reviewer's numeric id: gh api users/THEIR_LOGIN --jq .id
# Or just add them in the UI: Settings → Environments → external-signoff.

# 2. The block: require the sign-off status (and your CI) on the default branch.
gh api -X POST "repos/$REPO/rulesets" --input - <<'JSON'
{ "name": "Require manager sign-off on main", "target": "branch",
  "enforcement": "active",
  "conditions": { "ref_name": { "include": ["~DEFAULT_BRANCH"], "exclude": [] } },
  "rules": [{ "type": "required_status_checks",
    "parameters": { "strict_required_status_checks_policy": false,
      "required_status_checks": [ { "context": "Unit tests" },
                                  { "context": "manager-signoff" } ] } }] }
JSON

# 3. Pages, for the report site.
gh api -X POST "repos/$REPO/pages" -f build_type=workflow

# 4. Optional: let approval merge the PR with no further clicks.
gh api -X PATCH "repos/$REPO" -F allow_auto_merge=true
```

Then copy `.github/workflows/pr-queue.yml`, `.github/workflows/batch-signoff.yml`
and `scripts/` across.

### Adding or changing the reviewer

Settings → Environments → `external-signoff` → Required reviewers. Up to six
users or teams. **Any one of them approving is enough** — it is not consensus
logic. Turn on *Prevent self-review* if whoever triggered the run must not be
able to approve their own batch.

You can add them at any time; nothing else needs to change.

### Triggering a cycle by hand

Actions → **Batch sign-off** → *Run workflow*. Useful for releasing something
ahead of the weekly run, and for testing. If nothing is queued, the gated job is
skipped entirely and the reviewer is not disturbed.

## Operational notes

**Pushing during review is handled.** The batch records the exact commit each
pull request was reviewed at and re-reads the head before releasing it. If the
author pushed in the meantime, that pull request is **left queued** with a
warning in the log. An approval applies to the code that was actually read,
never to whatever arrived afterwards. A new push also creates a new commit with
no `manager-signoff` status, so it re-blocks on its own.

**Changing the sign-off workflow is a bootstrap problem.** The ruleset applies to
repository admins too, since no bypass actors are configured — so a pull request
that fixes `batch-signoff.yml` cannot be released by the broken workflow it is
fixing. Drop `manager-signoff` from the ruleset, land the fix, then put it back.
Add a bypass actor under Settings → Rules if you would rather have an escape
hatch.

**Auto-merge needs a required status check.** GitHub refuses to arm auto-merge on
a ruleset that only requires deployments, so the `Unit tests` entry is load
bearing, not decoration.

**Fork pull requests** get a read-only token and no secrets. The queue status
still posts, but do not add secrets to that job without understanding
`pull_request_target`.

**Notifications are GitHub's**, and depend on the reviewer's own settings. You
will not see them yourself while testing, because GitHub suppresses
notifications for your own activity — turn on Settings → Notifications →
*Include your own updates* if you want to. Do one dry run with the real
reviewer's account before relying on it.

## The synthetic project

A telemetry gateway: ingests spacecraft frames, decodes them into named
measurands, serves the latest values.

| Path | Purpose |
| --- | --- |
| `src/aurora/ingest.py` | Frame intake, de-duplication, drop accounting |
| `src/aurora/decode.py` | Frame → measurand decoding, checksum validation |
| `src/aurora/dictionary.py` | APID-to-measurand dictionary assembly |
| `src/aurora/api.py` | Read-only query surface |
| `src/aurora/config.py` | Runtime configuration |
| `tests/` | Unit tests |

```bash
python -m pytest tests/
```
