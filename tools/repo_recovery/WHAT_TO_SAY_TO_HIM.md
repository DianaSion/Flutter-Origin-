# What To Say To Him

Copy and send this exact message in the other Codespace chat:

```
Please run these commands and paste the outputs exactly:

1) gh auth status
2) gh api user --jq .login
3) gh codespace list
4) pwd
5) git remote -v
6) git branch -a
7) git log --oneline -n 20

Then create a full git backup bundle and show file size:

git bundle create litert-rescue-2026-06-10.bundle --all
ls -lh litert-rescue-2026-06-10.bundle

If this succeeds, tell me exactly where that bundle file is stored so I can download it.
```

If the bundle command fails, send this fallback:

```
Please run:
git status --short --branch
git rev-parse --is-inside-work-tree
```
