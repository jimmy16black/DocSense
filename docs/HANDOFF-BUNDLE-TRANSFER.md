# Transferring the DocSense work via git bundle (403 workaround)

Push failed: `Permission to jimmy16black/DocSense.git denied to gautamkale (403)`.
These artifacts move all 7 fix commits between machines/repos without write access.

## Artifacts
| File | Contents | Requires base commit? |
|---|---|---|
| `docsense-work.bundle` | Branch with full 7-commit history (7e905aa..HEAD), incremental on top of initial commit `43df795` | YES — receiving repo must contain `43df795` |
| `docsense-transfer-complete.bundle` | Single squashed commit `transfer` with the complete final tree (119 files, 24 passing tests) | NO — clones standalone |
| `docsense-work-6commits.patch` | All commits as `git am` patch series | Needs `43df795` for context |

Prerequisite check for the incremental bundle:
    git cat-file -t 43df795     # must print "commit" in the receiving repo

## Option A - Repo owner (jimmy16black): merge into main
    cd DocSense
    git fetch /path/to/docsense-work.bundle qwen-code-b06b924b-6de9-42c0-96c6-c47f5ac5d395
    git checkout -b fix/p0-production-readiness FETCH_HEAD
    git checkout main && git merge --ff-only fix/p0-production-readiness
    git push origin main

## Option B - Contributor (gautamkale): fork + PR
    gh repo fork jimmy16black/DocSense --clone
    cd DocSense
    git fetch /path/to/docsense-work.bundle qwen-code-b06b924b-6de9-42c0-96c6-c47f5ac5d395
    git branch fix/p0-production-readiness FETCH_HEAD
    git push origin fix/p0-production-readiness
    gh pr create --repo jimmy16black/DocSense --head gautamkale:fix/p0-production-readiness \
      --title "P0 production-readiness: issues #001 #002 #003 #005 #006"

## Option C - No shared history (shallow clone / diverged fork)
    git clone /path/to/docsense-transfer-complete.bundle docsense-final
    # gives you the exact working tree as one commit; then:
    cd docsense-final && git remote add target https://github.com/jimmy16black/DocSense.git
    git push target transfer:refs/heads/transfer/p0-work   # owner merges/rebases from it
    # OR replace base locally: cp -r . <fork> && commit there

## Option D - Patch series
    cd DocSense && git am --3way < docsense-work-6commits.patch
    # conflicts -> git am --abort, then: git apply --reject docsense-work-6commits.patch

## Verify after transfer
    cd backend && pip install -r requirements.txt -r requirements-dev.txt && pytest -q
    # expect: 24 passed
