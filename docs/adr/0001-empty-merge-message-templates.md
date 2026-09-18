# Empty merge message templates

Forgejo has no instance-wide setting to disable the `Reviewed-on:` trailer it
auto-appends to merge commit messages, only a per-repo template override
(`.forgejo/default_merge_message/*_TEMPLATE.md`). We added templates
containing a single newline for `MERGE`, `SQUASH`, `REBASE-MERGE`, and
`MANUALLY-MERGED`, which keeps Forgejo's default title but yields an empty
body — no trailer — on every merge going forward. Note the bootstrap gotcha:
Forgejo reads the template from the base branch as it existed *before* the
merge, so the PR that introduces these templates cannot benefit from its own
change.
