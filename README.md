# Antigravity Conversation Recovery

### Restore Missing Antigravity Chats on macOS and Windows

Recover missing Antigravity chats, restore sidebar order, and preserve usable titles from local artifacts.

This project rebuilds Antigravity's sidebar index from data that still exists on disk. It is designed to be safe first: if the script cannot preserve a conversation cleanly, it stops before writing.

Based on the original work by Salar, this repository is a refined version with safer macOS behavior, clearer recovery guardrails, and cross-platform documentation.

## Original Author Credit

Original project and initial release by Salar.

This repository builds on that work and refines it for safer macOS recovery, clearer public documentation, and stronger backup guardrails.

## What This Solves

| Problem | Status |
|---|---|
| Conversations missing from the sidebar | Supported |
| Sidebar order is wrong | Supported |
| Titles replaced by placeholders | Supported |
| Existing good titles get overwritten | Prevented |
| Partial repair causes more data loss | Prevented by backup + safety stop |

## Platform Support

| Platform | Status | Notes |
|---|---|---|
| Windows | Supported | Original target |
| macOS | Supported with safety limits | Stops if full sidebar metadata is missing |
| Linux | Path detection included | Less tested |

For the macOS-specific safety behavior, see [docs/macos-notes.md](docs/macos-notes.md).

## Quick Start

### Windows

1. Close Antigravity completely.
2. Run the packaged `.exe` from Releases, or use the source script.
3. Let the tool scan and rebuild the sidebar index.
4. Reopen Antigravity and verify the sidebar.

### macOS

1. Close Antigravity completely.
2. Double-click [run.command](run.command), or run `python3 rebuild_conversations.py`.
3. If the script reports skipped conversations, stop there and keep the backups.
4. Reopen Antigravity and verify what returned.

### From Source

```bash
python3 rebuild_conversations.py
```

No external dependencies are required. Python 3.7+ is enough.

## How It Works

Antigravity stores conversation state in two places:

- Conversation files on disk
- A sidebar index inside `state.vscdb`

The script reads the existing sidebar entries, matches them to local conversation files, sorts them newest-first, and writes the repaired ordering back to the database.

Title priority:

1. Brain artifact Markdown headings
2. Existing sidebar title already stored in the database
3. Date-based fallback title

## Safety Model

Before any write, the script creates:

- A full copy of `state.vscdb`
- A text backup of the original `trajectorySummaries` value

It also refuses to write if it detects conversations that exist on disk but do not have complete sidebar metadata available in the database. That guard is especially important on macOS.

## Output Markers

| Marker | Meaning |
|---|---|
| `[+]` | Title came from a brain artifact |
| `[~]` | Title came from an existing sidebar entry |
| `[?]` | Fallback title was used |
| `[!]` | Conversation was skipped to avoid lossy repair |

## Repository Layout

| File | Purpose |
|---|---|
| [rebuild_conversations.py](rebuild_conversations.py) | Main repair script |
| [run.bat](run.bat) | Windows launcher |
| [run.command](run.command) | macOS launcher |
| [docs/macos-notes.md](docs/macos-notes.md) | macOS limitations and recovery notes |

## Known Limitations

- The tool cannot yet synthesize every missing macOS sidebar entry from raw `.pb` files alone.
- If Antigravity has already lost the richer metadata for a conversation, the script will preserve safety over completeness.
- Some conversations may need manual investigation even when their raw files still exist.

## FAQ

**Do I need to restart my computer?**

Usually no. Fully closing and reopening Antigravity is normally enough.

**Can I run this while Antigravity is open?**

No. Close it first so the app does not overwrite the repaired index on exit.

**Why was a conversation skipped?**

The script found the raw conversation on disk, but not enough validated sidebar metadata to rebuild it safely.

## Publishing Notes

Do not commit local backup files such as `state.vscdb.backup.*` or `trajectorySummaries_backup.*`. They are user-specific recovery artifacts and are ignored by [.gitignore](.gitignore).

## License

MIT
