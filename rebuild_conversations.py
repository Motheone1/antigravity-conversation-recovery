"""
Antigravity Conversation Fix
=============================
Rebuilds the Antigravity conversation index so all your chat history
appears correctly — sorted by date (newest first) with proper titles.

Fixes:
  - Missing conversations in the sidebar
  - Wrong ordering (not sorted by date)
  - Missing/placeholder titles

Usage:
  1. CLOSE Antigravity completely
  2. Run this script (or use run.bat on Windows)
  3. Restart Antigravity
  4. Your conversations should appear, sorted by date

Requirements: Python 3.7+ (no external packages needed)
License: MIT
"""

import base64
import os
import shutil
import sqlite3
import sys
import time

# ─── Paths ────────────────────────────────────────────────────────────────────

TRAJECTORY_BACKUP_PREFIX = "trajectorySummaries_backup"
DB_BACKUP_PREFIX = "state.vscdb.backup"


def expand_path(path_value):
    """Expand env vars and ~ in either Windows or POSIX style."""
    if not path_value:
        return path_value

    expanded = os.path.expandvars(path_value)

    if "%" in expanded:
        for key, value in os.environ.items():
            expanded = expanded.replace(f"%{key}%", value)

    return os.path.expanduser(expanded)


def resolve_paths():
    """Return the best-known Antigravity paths for the current platform."""
    home = os.path.expanduser("~")
    conversations_dir = os.path.join(home, ".gemini", "antigravity", "conversations")
    brain_dir = os.path.join(home, ".gemini", "antigravity", "brain")

    if sys.platform == "darwin":
        db_path = os.path.join(
            home,
            "Library",
            "Application Support",
            "antigravity",
            "User",
            "globalStorage",
            "state.vscdb",
        )
    elif os.name == "nt":
        db_path = expand_path(r"%APPDATA%\antigravity\User\globalStorage\state.vscdb")
        conversations_dir = expand_path(r"%USERPROFILE%\.gemini\antigravity\conversations")
        brain_dir = expand_path(r"%USERPROFILE%\.gemini\antigravity\brain")
    else:
        db_path = os.path.join(
            home,
            ".config",
            "antigravity",
            "User",
            "globalStorage",
            "state.vscdb",
        )

    return db_path, conversations_dir, brain_dir


DB_PATH, CONVERSATIONS_DIR, BRAIN_DIR = resolve_paths()


# ─── Protobuf Varint Helpers ─────────────────────────────────────────────────

def encode_varint(value):
    """Encode an integer as a protobuf varint."""
    result = b""
    while value > 0x7F:
        result += bytes([(value & 0x7F) | 0x80])
        value >>= 7
    result += bytes([value & 0x7F])
    return result or b'\x00'


def decode_varint(data, pos):
    """Decode a protobuf varint at the given position. Returns (value, new_pos)."""
    result, shift = 0, 0
    while pos < len(data):
        b = data[pos]
        result |= (b & 0x7F) << shift
        if (b & 0x80) == 0:
            return result, pos + 1
        shift += 7
        pos += 1
    return result, pos


# ─── Protobuf Write Helpers ──────────────────────────────────────────────────

def encode_length_delimited(field_number, data):
    """Encode a length-delimited protobuf field (wire type 2)."""
    tag = (field_number << 3) | 2
    return encode_varint(tag) + encode_varint(len(data)) + data


def encode_string_field(field_number, string_value):
    """Encode a string as a protobuf field."""
    return encode_length_delimited(field_number, string_value.encode('utf-8'))


# ─── Title Extraction ────────────────────────────────────────────────────────

def extract_existing_entries(db_path):
    """
    Read complete trajectory entries already stored in the database.
    Returns a dict of {conversation_id: {"title": str, "entry": bytes}}.
    """
    entries = {}
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute(
            "SELECT value FROM ItemTable "
            "WHERE key='antigravityUnifiedStateSync.trajectorySummaries'"
        )
        row = cur.fetchone()
        conn.close()

        if not row or not row[0]:
            return entries

        decoded = base64.b64decode(row[0])
        pos = 0

        while pos < len(decoded):
            tag, pos = decode_varint(decoded, pos)
            wire_type = tag & 7

            if wire_type != 2:
                break

            length, pos = decode_varint(decoded, pos)
            entry = decoded[pos:pos + length]
            pos += length

            # Parse each entry for UUID (field 1) and info blob (field 2).
            ep, uid, info_b64 = 0, None, None
            while ep < len(entry):
                t, ep = decode_varint(entry, ep)
                fn, wt = t >> 3, t & 7
                if wt == 2:
                    l, ep = decode_varint(entry, ep)
                    content = entry[ep:ep + l]
                    ep += l
                    if fn == 1:
                        uid = content.decode('utf-8', errors='replace')
                    elif fn == 2:
                        sp = 0
                        _, sp = decode_varint(content, sp)
                        sl, sp = decode_varint(content, sp)
                        info_b64 = content[sp:sp + sl].decode('utf-8', errors='replace')
                elif wt == 0:
                    _, ep = decode_varint(entry, ep)
                else:
                    break

            if uid and info_b64:
                try:
                    info_data = base64.b64decode(info_b64)
                    ip = 0
                    _, ip = decode_varint(info_data, ip)
                    il, ip = decode_varint(info_data, ip)
                    title = info_data[ip:ip + il].decode('utf-8', errors='replace')
                    entries[uid] = {"title": title, "entry": entry}
                except Exception:
                    pass

    except Exception:
        pass

    return entries


def get_title_from_brain(conversation_id):
    """
    Try to extract a title from brain artifact .md files.
    Returns the first markdown heading found, or None.
    """
    brain_path = os.path.join(BRAIN_DIR, conversation_id)
    if not os.path.isdir(brain_path):
        return None

    for item in sorted(os.listdir(brain_path)):
        if item.startswith('.') or not item.endswith('.md'):
            continue
        try:
            filepath = os.path.join(brain_path, item)
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                first_line = f.readline().strip()
            if first_line.startswith('#'):
                return first_line.lstrip('# ').strip()[:80]
        except Exception:
            pass

    return None


def resolve_title(conversation_id, existing_entries):
    """
    Determine the best title for a conversation. Priority:
      1. Brain artifact .md heading
      2. Existing title from database (preserved from previous run)
      3. Fallback: date + short UUID
    Returns (title, source) where source is 'brain', 'preserved', or 'fallback'.
    """
    # Priority 1: Brain artifacts
    brain_title = get_title_from_brain(conversation_id)
    if brain_title:
        return brain_title, "brain"

    # Priority 2: Existing title from database
    if conversation_id in existing_entries:
        return existing_entries[conversation_id]["title"], "preserved"

    # Priority 3: Fallback with date
    conv_file = os.path.join(CONVERSATIONS_DIR, f"{conversation_id}.pb")
    if os.path.exists(conv_file):
        mod_time = time.strftime("%b %d", time.localtime(os.path.getmtime(conv_file)))
        return f"Conversation ({mod_time}) {conversation_id[:8]}", "fallback"

    return f"Conversation {conversation_id[:8]}", "fallback"


# ─── Protobuf Entry Builder ──────────────────────────────────────────────────

def build_trajectory_entry(conversation_id, title):
    """
    Build a single trajectory summary protobuf entry.
    Structure:
      field 1 (string) = conversation UUID
      field 2 (sub-message) = { field 1 (string) = base64(inner_info) }
      inner_info = { field 1 (string) = title }
    """
    inner_info = encode_string_field(1, title)
    info_b64 = base64.b64encode(inner_info).decode('utf-8')
    sub_message = encode_string_field(1, info_b64)

    entry = encode_string_field(1, conversation_id)
    entry += encode_length_delimited(2, sub_message)
    return entry


def build_index_from_existing_entries(conversation_ids, existing_entries):
    """
    Reorder only complete trajectory entries that already exist.
    Conversations without a complete stored entry are skipped for safety.
    Returns (encoded_bytes, skipped_ids, stats).
    """
    result = b""
    skipped_ids = []
    stats = {"brain": 0, "preserved": 0, "fallback": 0}
    markers = {"brain": "+", "preserved": "~", "fallback": "?"}

    print("  Building conversation index (newest first):")
    print("  " + "-" * 58)

    for i, cid in enumerate(conversation_ids, 1):
        title, source = resolve_title(cid, existing_entries)
        marker = markers[source]

        if cid not in existing_entries:
            skipped_ids.append(cid)
            print(f"    [{i:3d}] ! {title[:55]} (skipped: missing full metadata)")
            continue

        result += encode_length_delimited(1, existing_entries[cid]["entry"])
        stats[source] += 1
        print(f"    [{i:3d}] {marker} {title[:55]}")

    return result, skipped_ids, stats


def create_backups(db_path, existing_value):
    """Create full-database and trajectory backups before any write."""
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    script_dir = os.path.dirname(os.path.abspath(__file__))

    db_backup_path = os.path.join(script_dir, f"{DB_BACKUP_PREFIX}.{timestamp}")
    shutil.copy2(db_path, db_backup_path)

    trajectory_backup_path = None
    if existing_value:
        trajectory_backup_path = os.path.join(
            script_dir, f"{TRAJECTORY_BACKUP_PREFIX}.{timestamp}.txt"
        )
        with open(trajectory_backup_path, "w", encoding="utf-8") as f:
            f.write(existing_value)

    return db_backup_path, trajectory_backup_path


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print()
    print("=" * 62)
    print("   Antigravity Conversation Fix")
    print("   Rebuilds your conversation index — sorted by date")
    print("=" * 62)
    print()
    print(f"  Database path: {DB_PATH}")
    print(f"  Conversations: {CONVERSATIONS_DIR}")
    print(f"  Brain folder:  {BRAIN_DIR}")
    print()

    # ── Validate paths ──────────────────────────────────────────────────────

    if not os.path.exists(DB_PATH):
        print(f"  ERROR: Database not found at:")
        print(f"    {DB_PATH}")
        print()
        print("  Make sure Antigravity has been installed and opened at least once.")
        input("\n  Press Enter to close...")
        return 1

    if not os.path.isdir(CONVERSATIONS_DIR):
        print(f"  ERROR: Conversations directory not found at:")
        print(f"    {CONVERSATIONS_DIR}")
        input("\n  Press Enter to close...")
        return 1

    # ── Discover conversations ──────────────────────────────────────────────

    conv_files = [f for f in os.listdir(CONVERSATIONS_DIR) if f.endswith('.pb')]

    if not conv_files:
        print("  No conversations found on disk. Nothing to fix.")
        input("\n  Press Enter to close...")
        return 0

    # Sort by file modification time — newest first
    conv_files.sort(
        key=lambda f: os.path.getmtime(os.path.join(CONVERSATIONS_DIR, f)),
        reverse=True
    )
    conversation_ids = [f[:-3] for f in conv_files]

    print(f"  Found {len(conversation_ids)} conversations on disk")
    print()

    # ── Preserve existing titles ────────────────────────────────────────────

    print("  Reading existing entries from database...")
    existing_entries = extract_existing_entries(DB_PATH)
    print(f"  Found {len(existing_entries)} complete entries to preserve")
    print()

    # ── Build the new index ─────────────────────────────────────────────────

    result, skipped_ids, stats = build_index_from_existing_entries(
        conversation_ids, existing_entries
    )

    print("  " + "-" * 58)
    print("  Legend: [+] brain artifact  [~] preserved  [?] fallback  [!] skipped")
    print(
        "  Totals: "
        f"{stats['brain']} from brain, "
        f"{stats['preserved']} preserved, "
        f"{stats['fallback']} fallback, "
        f"{len(skipped_ids)} skipped"
    )
    print()

    if skipped_ids:
        print("  Safety stop: some conversations exist on disk but do not have")
        print("  complete sidebar metadata in the current database.")
        print("  No changes were written so nothing is lost.")
        print()
        print("  Missing full metadata for:")
        for cid in skipped_ids:
            print(f"    - {cid}")
        print()
        input("  Press Enter to close...")
        return 1

    # ── Backup current data ─────────────────────────────────────────────────

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute(
        "SELECT value FROM ItemTable "
        "WHERE key='antigravityUnifiedStateSync.trajectorySummaries'"
    )
    row = cur.fetchone()

    db_backup_path, trajectory_backup_path = create_backups(DB_PATH, row[0] if row else None)
    print(f"  Full database backup saved to: {os.path.basename(db_backup_path)}")
    if trajectory_backup_path:
        print(
            "  Trajectory backup saved to: "
            f"{os.path.basename(trajectory_backup_path)}"
        )

    # ── Write the new index ─────────────────────────────────────────────────

    encoded = base64.b64encode(result).decode('utf-8')

    if row:
        cur.execute(
            "UPDATE ItemTable SET value=? "
            "WHERE key='antigravityUnifiedStateSync.trajectorySummaries'",
            (encoded,)
        )
    else:
        cur.execute(
            "INSERT INTO ItemTable (key, value) "
            "VALUES ('antigravityUnifiedStateSync.trajectorySummaries', ?)",
            (encoded,)
        )

    conn.commit()
    conn.close()

    # ── Done ────────────────────────────────────────────────────────────────

    total = len(conversation_ids)
    print()
    print("  " + "=" * 58)
    print(f"  SUCCESS! Rebuilt index with {total} conversations.")
    print("  " + "=" * 58)
    print()
    print("  NEXT STEPS:")
    print("    1. Make sure Antigravity is fully closed")
    print("    2. Reopen Antigravity")
    print("    3. Conversations should appear sorted by date")
    print()
    input("  Press Enter to close...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
