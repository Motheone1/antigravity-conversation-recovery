# macOS Notes

This repository supports macOS, but the recovery behavior is intentionally conservative.

## Why macOS is Different

On some macOS installs, the Antigravity sidebar database stores richer per-conversation metadata than the older Windows-only rebuild flow expected. If that metadata is missing for a conversation, writing a synthetic entry can hide the full sidebar instead of restoring it.

## Current Safety Rule

The script will only rewrite conversations that already have complete sidebar entries in the database.

If a conversation exists on disk but does not have complete sidebar metadata, the script will:

1. Detect it
2. Print the missing conversation IDs
3. Stop without writing anything

That behavior is deliberate. It prevents partial repairs from making things worse.

## What Still Works

- Reordering existing sidebar entries
- Preserving existing titles
- Reading macOS Antigravity paths automatically
- Creating full database backups before any write

## What Does Not Yet Work Automatically

- Reconstructing brand-new macOS sidebar entries from only `.pb` conversation files
- Rebuilding missing entries when the database no longer contains the original metadata blob

## Recommended Workflow

1. Close Antigravity completely
2. Run the script
3. If the script reports skipped conversations, do not force it
4. Keep the generated backups
5. Reopen Antigravity and verify what was restored

## Backups

The script creates:

- a full `state.vscdb` copy
- a text backup of the original `trajectorySummaries` value

Those backups are meant for local recovery only and should not be committed to Git.
