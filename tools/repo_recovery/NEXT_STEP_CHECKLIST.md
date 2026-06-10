# Next Step Checklist

## 1) Confirm mirrors exist (already completed)

Run:

```bash
ls -lah tools/repo_recovery/output/mirrors
```

## 2) Put your downloaded bundle into this repo

Expected location:

`tools/repo_recovery/incoming/`

Example filename:

`litert-rescue-2026-06-10.bundle`

## 3) Import that bundle in one command

```bash
python3 tools/repo_recovery/import_bundle.py \
  --bundle tools/repo_recovery/incoming/litert-rescue-2026-06-10.bundle
```

## 4) Open the import report

Report path:

`tools/repo_recovery/output/bundle_import_report.md`

This report lists recovered branches/refs and commit subjects.

## 5) Ask Copilot to integrate recovered branch

Say:

"Integrate branch <branch-name> from recovered bundle into my working branch, preserve my staged files, and open a PR if branch rules block direct push."
