# 🔧 QUICK FIX: Migration Error

## Your Error:
```
relation "quiz_session_roster" does not exist
```

## Quick Fix (Choose ONE):

### ⚡ FASTEST: Run Auto-Fix Script

```bash
cd ata-backend
python fix_migrations.py
python -m alembic upgrade head
```

This automatically detects your migration IDs and fixes the chain.

---

### 🎯 MANUAL FIX: Update Down Revision

1. **Check your initial migration ID:**
   ```bash
   cd ata-backend
   python -m alembic history
   ```

   Look for the FIRST migration (the one with no parent).
   In your case, it's probably: `07d7d2f65290`

2. **Edit roster migration:**
   Open: `ata-backend/alembic/versions/20251117_060108_add_quiz_roster_tracking.py`

   Find line 21:
   ```python
   down_revision: Union[str, Sequence[str], None] = '018e9779debd'
   ```

   Change to YOUR initial migration ID:
   ```python
   down_revision: Union[str, Sequence[str], None] = '07d7d2f65290'
   ```

3. **Save and run:**
   ```bash
   python -m alembic upgrade head
   ```

---

### 🔄 FRESH START: Reset Database (Development Only!)

**⚠️ WARNING: This deletes all data!**

```bash
# In psql or database tool
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;

# Then run migrations
cd ata-backend
python -m alembic stamp head
python -m alembic upgrade head
```

---

## Why This Happens

Your initial migration file has a different ID than expected. This happens when:
- You ran `alembic revision --autogenerate` after models were updated
- You're working with a different database/branch state

The roster migration tries to build on migration `018e9779debd`, but yours is `07d7d2f65290`.

---

## After Fixing

Verify it worked:
```bash
python -m alembic current
```

Should show:
```
20251117_060108 (head)
```

Then start your backend:
```bash
python -m uvicorn app.main:app --reload
```

---

## Need More Help?

See detailed guide: `MIGRATION_FIX_GUIDE.md`
