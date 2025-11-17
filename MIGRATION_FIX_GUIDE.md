# MIGRATION FIX GUIDE

## Problem Analysis

Your error shows:
```
relation "quiz_session_roster" does not exist
```

This happens because:
1. Your initial migration (`07d7d2f65290`) was auto-generated AFTER models were updated
2. It's trying to create `quiz_participants` with foreign keys to `quiz_session_roster`
3. But `quiz_session_roster` doesn't exist yet (it's created in the NEXT migration)

## Solution

Follow these steps to fix the migration order:

### Option 1: Update Down Revision (RECOMMENDED)

1. **Find your actual initial migration ID:**
   ```bash
   cd ata-backend
   python -m alembic history
   ```

2. **Update the roster migration:**
   Edit `ata-backend/alembic/versions/20251117_060108_add_quiz_roster_tracking.py`

   Change line 21 from:
   ```python
   down_revision: Union[str, Sequence[str], None] = '018e9779debd'
   ```

   To:
   ```python
   down_revision: Union[str, Sequence[str], None] = '07d7d2f65290'  # Your actual migration ID
   ```

3. **Run migrations:**
   ```bash
   python -m alembic upgrade head
   ```

### Option 2: Fresh Database (If starting fresh)

If this is a development database with no production data:

1. **Drop all tables:**
   ```sql
   -- Connect to your database
   DROP SCHEMA public CASCADE;
   CREATE SCHEMA public;
   GRANT ALL ON SCHEMA public TO your_user;
   GRANT ALL ON SCHEMA public TO public;
   ```

2. **Delete alembic version table:**
   ```bash
   cd ata-backend
   python -m alembic stamp head
   ```

3. **Run migrations from scratch:**
   ```bash
   python -m alembic upgrade head
   ```

### Option 3: Remove Problematic Foreign Key from Initial Migration

Edit your initial migration file to remove the foreign key that references a non-existent table:

1. **Open:** `ata-backend/alembic/versions/07d7d2f65290_initial_database_schema.py`

2. **Find the `quiz_participants` table creation** (around line 242)

3. **Remove these lines if they exist:**
   ```python
   sa.Column('is_outsider', sa.Boolean(), nullable=False),
   sa.Column('roster_entry_id', sa.String(), nullable=True),
   sa.ForeignKeyConstraint(['roster_entry_id'], ['quiz_session_roster.id'], ondelete='SET NULL'),
   ```

4. **Save and run:**
   ```bash
   python -m alembic upgrade head
   ```

## Verification

After fixing, verify migrations work:

```bash
cd ata-backend
python -m alembic current
python -m alembic history
```

You should see both migrations in order:
```
07d7d2f65290 -> 20251117_060108 (head)
```

## Why This Happened

When you updated the SQLAlchemy models to add `is_outsider` and `roster_entry_id` to `QuizParticipant`, then ran `alembic revision --autogenerate`, Alembic saw these new columns and tried to add them to an initial migration. This created a circular dependency:
- Initial migration needs `quiz_session_roster` to exist (for foreign key)
- But `quiz_session_roster` is created in the roster migration
- Which runs AFTER the initial migration

## Prevention

To avoid this in the future:
1. Always check `down_revision` matches your last migration
2. Don't run `alembic revision --autogenerate` after updating models - use the provided migrations
3. If you need custom migrations, create them manually with proper ordering
