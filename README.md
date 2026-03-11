# Antigravity Conversation Fix

Fixes missing and unordered conversation history in **Antigravity** (the Google DeepMind AI coding assistant).

## The Problem

Antigravity sometimes loses your conversation sidebar — conversations disappear, show in wrong order, or display placeholder titles instead of real names. This happens because the internal conversation index (`state.vscdb`) gets corrupted or out of sync with the actual conversation files on disk.

## What This Tool Does

- **Restores all conversations** from disk back into the sidebar
- **Sorts by date** (newest first) so your most recent chats appear on top
- **Preserves real titles** — extracts names from brain artifacts and keeps existing titles from the database
- **Backs up** your current index before making changes (saved as `trajectorySummaries_backup.txt`)

## Requirements

- **Python 3.7+** (no external packages needed — uses only Python standard library)
- **Windows** (paths are Windows-specific)

## Usage

### Option 1: Double-click (easiest)

1. **Close Antigravity completely** (File → Exit, or kill `antigravity.exe` from Task Manager)
2. Double-click **`run.bat`**
3. **Reboot your PC** (full restart, not just app restart)
4. Open Antigravity — your conversations should appear, sorted by date

### Option 2: Command line

```
python rebuild_conversations.py
```

## How It Works

Antigravity stores conversation data in two places:

| Location | Contains |
|---|---|
| `%USERPROFILE%\.gemini\antigravity\conversations\*.pb` | Encrypted conversation data (messages, code, etc.) |
| `%APPDATA%\antigravity\User\globalStorage\state.vscdb` | SQLite database with the sidebar index (which conversations to show, their titles, order) |

When the index gets corrupted, conversations exist on disk but don't appear in the sidebar. This tool scans the conversation files, rebuilds the index sorted by modification date, and writes it back to the database.

**Title resolution priority:**
1. Brain artifact `.md` headings (from `%USERPROFILE%\.gemini\antigravity\brain\`)
2. Existing titles already in the database (preserved across re-runs)
3. Fallback: `Conversation (date) short-uuid`

## Output Legend

When the tool runs, each conversation is marked with its title source:

| Marker | Meaning |
|---|---|
| `[+]` | Title extracted from brain artifact |
| `[~]` | Title preserved from existing database |
| `[?]` | Fallback title (no other source available) |

## FAQ

**Q: Why do some conversations show as "Conversation (Mar 10) abc12345"?**
A: These conversations don't have brain artifacts (`.md` files) and weren't in the database with a real title. The app generates titles internally — if the index was already corrupted before running this tool, those titles are lost. Future re-runs will preserve any titles the app generates.

**Q: Do I really need to reboot?**
A: Yes. Antigravity caches the index in memory and writes it back on shutdown. A simple app restart isn't enough — the OS-level file locks need to fully release.

**Q: Is this safe?**
A: Yes. The tool backs up your current index before making changes. Your actual conversation data (the `.pb` files) is never modified — only the sidebar index is rebuilt.

**Q: Can I run this multiple times?**
A: Absolutely. Each run preserves existing titles and re-sorts by date. It's safe to re-run whenever your sidebar gets out of sync.

## File Structure

```
Antigravity Conversation Fix/
├── rebuild_conversations.py    # Main script
├── run.bat                     # Windows launcher
└── README.md                   # This file
```

## License

MIT — use it, share it, modify it.

---

**⭐ If this tool helped you, please star the repo so other users can find it!**
