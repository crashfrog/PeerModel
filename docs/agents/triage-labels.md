# Triage Labels

The `triage` skill moves issues through a five-state machine using these labels:

| Label | Meaning | Next action |
|-------|---------|-------------|
| `needs-triage` | Maintainer needs to evaluate | Review, assign label based on priority/scope |
| `needs-info` | Waiting on reporter | Comment asking for details; re-triage when answered |
| `ready-for-agent` | Fully specified, AFK-ready | Autonomous agent can pick up; no human context needed |
| `ready-for-human` | Needs human implementation | Assign to team member or wait for bandwidth |
| `wontfix` | Will not be actioned | Close the issue |

## Label creation

These labels are created automatically by `triage` skill on first use. No manual setup required.
