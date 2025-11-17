#!/usr/bin/env python3
"""
Automatic Migration Fix Script

This script fixes the migration ordering issue by:
1. Detecting the actual initial migration ID
2. Updating the roster migration to reference it correctly
3. Verifying the migration chain

Usage:
    python fix_migrations.py
"""

import os
import re
import sys
from pathlib import Path


def find_migrations_dir():
    """Find the alembic versions directory."""
    script_dir = Path(__file__).parent
    versions_dir = script_dir / "alembic" / "versions"

    if not versions_dir.exists():
        print(f"❌ Error: Migrations directory not found at {versions_dir}")
        sys.exit(1)

    return versions_dir


def find_initial_migration(versions_dir):
    """Find the initial migration (one with down_revision = None)."""
    for file in versions_dir.glob("*.py"):
        if file.name == "__init__.py":
            continue

        with open(file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Look for down_revision = None
        if "down_revision: Union[str, Sequence[str], None] = None" in content or \
           "down_revision = None" in content:
            # Extract revision ID
            match = re.search(r"revision:\s*str\s*=\s*['\"]([^'\"]+)['\"]", content)
            if match:
                return match.group(1), file

    return None, None


def find_roster_migration(versions_dir):
    """Find the roster tracking migration."""
    for file in versions_dir.glob("*roster_tracking.py"):
        if file.name == "__init__.py":
            continue
        return file

    return None


def update_roster_migration(roster_file, correct_down_revision):
    """Update the roster migration's down_revision."""
    with open(roster_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find current down_revision
    current_match = re.search(r"down_revision:\s*Union\[str,\s*Sequence\[str\],\s*None\]\s*=\s*['\"]([^'\"]+)['\"]", content)

    if not current_match:
        print("❌ Error: Could not find down_revision in roster migration")
        return False

    current_down = current_match.group(1)

    if current_down == correct_down_revision:
        print(f"✅ Roster migration already points to correct revision: {correct_down_revision}")
        return True

    print(f"📝 Updating roster migration:")
    print(f"   From: {current_down}")
    print(f"   To:   {correct_down_revision}")

    # Replace down_revision
    new_content = re.sub(
        r"(down_revision:\s*Union\[str,\s*Sequence\[str\],\s*None\]\s*=\s*['\"])[^'\"]+(['\"])",
        rf"\g<1>{correct_down_revision}\g<2>",
        content
    )

    # Write back
    with open(roster_file, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print("✅ Roster migration updated successfully!")
    return True


def check_initial_migration_for_roster_columns(initial_file):
    """Check if initial migration has roster columns (which would cause the error)."""
    with open(initial_file, 'r', encoding='utf-8') as f:
        content = f.read()

    has_roster_entry_id = 'roster_entry_id' in content
    has_is_outsider = 'is_outsider' in content
    has_roster_fk = 'quiz_session_roster' in content and 'quiz_participants' in content

    issues = []

    if has_roster_entry_id:
        issues.append("- Contains 'roster_entry_id' column")
    if has_is_outsider:
        issues.append("- Contains 'is_outsider' column")
    if has_roster_fk:
        issues.append("- Contains foreign key to 'quiz_session_roster'")

    if issues:
        print("\n⚠️  WARNING: Your initial migration contains roster-related columns:")
        for issue in issues:
            print(f"   {issue}")
        print("\n   These should be in the roster migration, not the initial migration.")
        print("   This is likely why you're getting the error.")
        print("\n   Recommended actions:")
        print("   1. Edit the initial migration to remove these lines")
        print("   2. OR drop your database and run migrations fresh")
        print("   3. OR see MIGRATION_FIX_GUIDE.md for detailed instructions")
        return False

    return True


def main():
    print("🔍 Quiz Roster Migration Fix Script")
    print("=" * 60)

    # Find migrations directory
    versions_dir = find_migrations_dir()
    print(f"✅ Found migrations directory: {versions_dir}")

    # Find initial migration
    initial_id, initial_file = find_initial_migration(versions_dir)

    if not initial_id:
        print("❌ Error: Could not find initial migration (one with down_revision = None)")
        sys.exit(1)

    print(f"✅ Found initial migration: {initial_id}")
    print(f"   File: {initial_file.name}")

    # Check if initial migration has problematic columns
    is_clean = check_initial_migration_for_roster_columns(initial_file)

    # Find roster migration
    roster_file = find_roster_migration(versions_dir)

    if not roster_file:
        print("❌ Error: Could not find roster tracking migration")
        sys.exit(1)

    print(f"✅ Found roster migration: {roster_file.name}")

    # Update roster migration
    success = update_roster_migration(roster_file, initial_id)

    if success and is_clean:
        print("\n" + "=" * 60)
        print("✅ Migration chain fixed successfully!")
        print("\nNext steps:")
        print("   1. Run: python -m alembic upgrade head")
        print("   2. Verify: python -m alembic current")
    elif success and not is_clean:
        print("\n" + "=" * 60)
        print("⚠️  Migration chain updated, but initial migration has issues")
        print("   Please see warnings above and MIGRATION_FIX_GUIDE.md")
    else:
        print("\n" + "=" * 60)
        print("❌ Failed to fix migrations")
        print("   Please see MIGRATION_FIX_GUIDE.md for manual fix instructions")
        sys.exit(1)


if __name__ == "__main__":
    main()
