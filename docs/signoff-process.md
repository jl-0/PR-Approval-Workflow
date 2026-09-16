# Manager sign-off process

## What this does

Code review happens as normal: developers open pull requests, the team reviews
them. What changes is that a pull request cannot merge until a nominated manager
has signed off — and they do that **once a week for everything at once**, not
once per pull request.

The manager never reviews a diff. They read a page of tables and press one
button.

## The mechanism

GitHub calls this a *deployment*, but nothing is deployed. A "deployment" is
simply a job that names an **environment**, and an environment can require
named reviewers before any job referencing it may start. That is the gate.

What that gate then does is flip a commit status on each reviewed pull request,
and a branch rule requires that status. So one approval releases many pull
requests.

## What the reviewer sees

They get one email per cycle: *"Deployment review required."* It links to the
workflow run, where they find:

1. The **report** rendered directly on the page, above the paused job — every
   pull request waiting, the work items they close, and all their tags.
2. A link to the same report as a **GitHub Pages site**, if they prefer a clean
   page.
3. A **Review deployments** button. They tick `external-signoff`, optionally
   leave a comment, and press **Approve and deploy** or **Reject**.

Approval releases every pull request in that report. Rejection fails the job,
nothing is released, and the same set reappears in the next cycle.

## Access

A required reviewer needs **read access only**. They cannot push, merge, or
change the workflow. On a public repository this protection rule is available on
every plan tier.

## Adding the reviewer

Settings → Environments → `external-signoff` → Required reviewers → add up to
six people or teams. If several are listed, **any one** of them approving is
enough; that is not consensus logic.

Turn on *Prevent self-review* if the person who triggered the run must not be
able to approve their own batch.

## The summary at the top of the report

Every report opens with a short bulleted overview: how much merged, what needs a
closer look, what the batch consists of, and which pull requests closed no
tracked work item. That last point is the traceability question an assessor
asks, so it is stated rather than left to be noticed.

This is derived directly from the pull request data — no model, no network, no
cost, nothing to configure. It is always present.

### Turning on a written summary (optional)

A model can write that overview in prose instead.

The free option is gone: **GitHub Models was retired on 30 July 2026**, taking
the free `models: read` inference endpoint with it. Its replacement is Copilot
CLI, which needs a token belonging to an account with Copilot access.

To enable it, add a repository secret named `COPILOT_PAT` holding a personal
access token for an account with Copilot. The workflow detects the secret and
uses it; with no secret, the steps are skipped entirely and the derived summary
is used instead.

Both the Copilot step and its install step are `continue-on-error`, and the
report labels which kind of summary it carries. A quota exhaustion or an outage
degrades the wording of one paragraph — it never blocks a sign-off, and the
tables come straight from GitHub's API either way.

## How the gate works

Pull requests are held until a single batched approval releases them. Nobody is
notified per pull request.

```
PR opened ──► Queue for sign-off posts a PENDING manager-signoff status
              (the branch rule blocks the merge; no reviewer involved yet)

   ...PRs accumulate through the week...

Monday 14:00 UTC (or you trigger it) ──► Batch sign-off
   collect ──► publish to Pages ──► signoff  ← ONE approval, all PRs
                                       │
                                       └──► flips every reviewed PR's
                                            manager-signoff to success
```

### What holds a pull request

The branch rule *Require manager sign-off on main* requires two status checks:

- `Unit tests` — ordinary CI.
- `manager-signoff` — posted as **pending** by `pr-queue.yml` when the pull
  request opens, and flipped to **success** only by an approved batch.

A pending status is what blocks the merge. It also gives the author a readable
reason on the pull request — *"Queued for the next sign-off batch"* — rather
than an unexplained blocked merge button.

### What the reviewer does

Once a cycle they get one notification for one workflow run. They read the
report — on the run summary, or as the [Pages site](https://jl-0.github.io/PR-Approval-Workflow/)
linked beside it — and approve `external-signoff` once. Every pull request in
that report becomes mergeable.

If nothing is queued, the `signoff` job is skipped entirely and nobody is
disturbed.

### Pushing during review

The batch records the exact commit each pull request was reviewed at. Before
releasing one, the approval step re-reads its current head. If the author pushed
in the meantime the pull request is **left queued**, with a warning in the run
log, and waits for the next cycle.

That is the point of the whole mechanism: an approval applies to the code that
was actually read, never to whatever happened to arrive afterwards. A new push
also produces a new commit with no `manager-signoff` status, so it re-blocks on
its own.

### Triggering a cycle by hand

Actions → **Batch sign-off** → *Run workflow*. Useful for releasing something
before the weekly run, and for testing.

## Why not gate each pull request individually

An earlier version put the environment gate on a `pull_request` workflow. It
worked — the merge button was genuinely blocked — but every pull request created
its own pending deployment and its own email. Ten open pull requests meant ten
approvals. Batching trades an immediate gate for one review a week, which is the
point of having a manager sign off on a body of work rather than on each change.

## Notes and limits

**Fork pull requests.** A `pull_request` workflow from a fork gets a read-only
token and no secrets. The report still builds, but if you later add secrets to
that job, switch to `pull_request_target` and understand what that exposes.

**Direct pushes to `main`.** The ruleset applies to everyone including repository
admins, since no bypass actors are configured. Every change goes through a pull
request and therefore through a sign-off batch. Add a bypass actor under
Settings → Rules if you need an escape hatch.

**Required reviewers are not consensus.** If several are listed, any one of them
approving is enough.
