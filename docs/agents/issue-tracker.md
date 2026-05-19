# Issue Tracker — GitHub

Issues for this project live in GitHub Issues at https://github.com/crashfrog/PeerModel/issues.

## Skills that interact with GitHub Issues

- `to-issues` — break plans into GitHub issues
- `triage` — evaluate and label issues
- `to-prd` — publish PRDs as GitHub issues
- `qa` — create bug reports and test tracking issues

## Commands for manual interaction

```bash
# View an issue
gh issue view <number>

# Create an issue
gh issue create --title "..." --body "..."

# Add label
gh issue edit <number> --add-label "label-name"

# List issues with a label
gh issue list --label "ready-for-agent"
```

See `gh issue --help` for full reference.
