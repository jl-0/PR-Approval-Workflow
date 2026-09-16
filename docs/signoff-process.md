# Manager sign-off process

## What this does

Code review happens as normal: developers open pull requests, the team reviews
them, they merge into `main`. Nothing about that changes.

Separately, once a week, a workflow gathers everything that merged since the
last approval, writes a plain-English report, publishes it as a web page, and
then **stops** — waiting for a nominated manager to press Approve.

The manager never reviews a diff. They read a page of tables and press a button.

## The mechanism

GitHub calls this a *deployment*, but nothing is deployed. A "deployment" is
simply a job that names an **environment**, and an environment can require
named reviewers before any job referencing it may start. That is the whole trick.

```
report ──► publish ──► signoff
(tables)   (Pages)     (PAUSED — waiting for the manager)
```

The three jobs are separate deliberately. An environment gate pauses a job
*before its first step runs*, so if the report were generated inside the gated
job, the reviewer would have to approve before they could read anything.

## What the reviewer sees

They get an email: *"Deployment review required."* It links to the workflow run,
where they find:

1. The **report** rendered directly on the page, above the paused job — tables of
   pull requests, the work items they closed, and every tag involved.
2. A link to the same report as a **GitHub Pages site**, if they prefer a clean page.
3. A **Review deployments** button. They tick `external-signoff`, optionally leave
   a comment, and press **Approve and deploy** or **Reject**.

Approval writes a `signoff-<date>-<time>` tag with their decision recorded
against it, and the next week's window starts from that tag — so nothing can
silently skip a review cycle.

Rejection fails the job. The tag is not written, so the same batch reappears in
the next run.

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

## Optionally: blocking merges on sign-off

The setup above is a periodic batch review, which is usually what people want.
If instead a *single* pull request must not merge until the manager signs off:

1. Change the trigger to `pull_request`.
2. In branch protection for `main` (Settings → Rules), enable **Require
   deployments to succeed before merging** and select `external-signoff`.

The pull request then stays unmergeable until the manager approves the
deployment. Combine with auto-merge and it merges itself the moment both the
team review and the sign-off are green.
