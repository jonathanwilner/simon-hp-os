# Fleet release protections

The repository keeps its GitHub rulesets in `.github/rulesets/`. Check drift with
`python3 scripts/fleet-rulesets.py`. Apply changes with
`python3 scripts/fleet-rulesets.py --apply`. The command uses the authenticated
GitHub CLI account, which needs repository Administration write permission.
It manages only the two named fleet rulesets, preserves unrelated rulesets,
refuses duplicate names, and verifies every change by reading it back.

* `fleet-immutable-tags` prevents updates and deletion of `refs/tags/fleet-*`.
  Creation remains allowed so the promotion workflow can create release tags.
* `fleet-stable-gates` prevents deletion and non-fast-forward updates of
  `refs/heads/fleet-stable`. Creation and later updates require both `validate`
  matrix job results and both `fleet/canary/` statuses on the target commit.
  CI checks are bound to the GitHub Actions integration ID 15368. Canary
  statuses currently come from the trusted controller's personal token.

Neither ruleset grants bypass actors, including administrators or Actions.
Administrators can still edit rulesets. The controller's status-writing
credential remains a trust boundary: GitHub verifies the required context,
while the controller verifies the live launcher evidence before posting it.
The promotion workflow additionally verifies the exact main-push workflow run
and HTTPS evidence URLs. Rulesets alone cannot verify those evidence contents.
Tag creation alone is not release acceptance; consumers follow `fleet-stable`.

Keep the required CI contexts aligned with matrix job names when changing the
workflow. A renamed job causes promotion to fail closed until this configuration
is reconciled. No automatic deployment follows a ruleset update.

API schema: [GitHub repository rulesets REST API](https://docs.github.com/en/rest/repos/rules#create-a-repository-ruleset).
The API version used by the reconciler is `2026-03-10`.
