# 🚀 QUICK TEST GUIDE - Auto-Advance Fix

**Branch:** `claude/analyze-readme-test-code-016Ppcg8WB5GaPUiJS7jCBLN`
**Latest Commit:** `683a6d8`

---

## ⚡ Quick Start (5 Minutes)

### Step 1: Pull & Restart

```bash
# Pull latest changes
cd ata-project
git fetch origin
git checkout claude/analyze-readme-test-code-016Ppcg8WB5GaPUiJS7jCBLN
git pull

# Restart backend
cd ata-backend
pkill -f uvicorn
uvicorn app.main:app --reload

# Restart frontend (in new terminal)
cd ata-frontend
npm run dev
```

### Step 2: Create Test Quiz

1. Login to teacher account
2. Create new quiz: "Test Auto-Advance"
3. Add 2 questions (multiple choice)
4. Each question: 30 second timer
5. Save and publish

### Step 3: Start Quiz Session

1. Click "Start Quiz Session"
2. **IMPORTANT**: Check that "Auto-advance" switch is **ON** (it should be by default now!)
3. **IMPORTANT**: Check browser console (F12), should see:
   ```
   [QuizHost] 🚀 Auto-enabling auto-advance for session: {session_id}
   [QuizHost] ✅ Auto-advance enabled successfully
   ```
4. Click "Start Quiz" button

### Step 4: Join as Students

1. Open 2 incognito windows
2. Join quiz with room code
3. Student A: Submit answer at ~15 seconds
4. Student B: Don't submit (let timer expire)

### Step 5: Watch the Magic ✨

**At T+30s (timer expires):**
- ✅ Student A should see: "Answer submitted! Next question in 10s"
- ✅ Student B should see: "Time expired! Next question in 10s"
- ✅ **BOTH** should see countdown: 10s → 9s → 8s → ...
- ✅ Teacher should see countdown in their dashboard

**At T+40s (cooldown finishes):**
- ✅ Question 2 appears **automatically** for all students
- ✅ No teacher intervention needed!

**After Question 2 finishes:**
- ✅ Quiz ends automatically
- ✅ Teacher redirected to analytics page
- ✅ Students see final leaderboard

---

## 🔍 Debugging Checklist

### If Auto-Advance Still Doesn't Work:

**1. Check Frontend Console (F12)**
```
Expected logs:
✅ [QuizHost] 🚀 Auto-enabling auto-advance for session: ...
✅ [QuizHost] ✅ Auto-advance enabled successfully
```

**If NOT seeing these:**
- Hard refresh (Ctrl+Shift+F5)
- Clear browser cache
- Check: Is switch ON by default?

**2. Check Backend Logs**
```bash
# In backend terminal, look for:
grep -E "\[StartSession\]|\[AutoAdvance\]" logs/app.log

Expected logs:
✅ [StartSession] auto_advance_enabled: True
✅ [AutoAdvance] ✅ Job added successfully!
✅ [AutoAdvance] ========== EXECUTING AUTO-ADVANCE ==========
```

**If NOT seeing these:**
- Check: Did backend restart?
- Check: Did you pull latest code?
- Check: Is session status 'waiting' before clicking "Start Quiz"?

**3. Check Scheduler**
```bash
# On backend startup, should see:
grep "Scheduler" logs/app.log

Expected:
✅ [SCHEDULER] Scheduler started
```

---

## 📊 What Changed?

### Frontend (QuizHost.jsx):

**Change 1:** Auto-advance now **ON by default**
```javascript
// Line 148
const [autoAdvanceEnabled, setAutoAdvanceEnabled] = useState(true); // ← Changed from false
```

**Change 2:** Auto-enable when session loads
```javascript
// Lines 208-236
useEffect(() => {
  // Automatically calls toggleAutoAdvance(sessionId, true, 10)
  // when session is in 'waiting' status
}, [session?.id, session?.status]);
```

### Backend (quiz_service.py):

**No changes needed!** The WebSocket broadcast fix from commit `3e685e1` is still valid. The scheduler just needed to be enabled.

---

## 🎯 Success Criteria

All of these must work:

- [ ] Switch shows ON by default when opening QuizHost
- [ ] Browser console logs: "Auto-enabling auto-advance"
- [ ] Backend logs: "[StartSession] auto_advance_enabled: True"
- [ ] Backend logs: "[AutoAdvance] Job added successfully!"
- [ ] Students who submit early see cooldown countdown
- [ ] Students who don't submit see cooldown countdown
- [ ] Countdown displays: 10 → 9 → 8 → ... → 1
- [ ] Question auto-advances when countdown reaches 0
- [ ] Quiz auto-ends after last question
- [ ] Teacher redirected to analytics page

---

## 🆘 Emergency Rollback

If something breaks:

```bash
# Rollback to previous commit
git reset --hard 4be4c9e

# Or just disable auto-advance manually:
# In QuizHost.jsx line 148, change back to:
const [autoAdvanceEnabled, setAutoAdvanceEnabled] = useState(false);

# Then toggle it manually before starting each quiz
```

---

## 📞 Still Not Working?

Read the full documentation:
- **COMPREHENSIVE_AUTO_ADVANCE_FIX.md** - Complete root cause analysis
- **QUIZ_AUTO_ADVANCE_FIX_SUMMARY.md** - Original bug report

**Common Issues:**

1. **Frontend not updated:** Clear browser cache, hard refresh
2. **Backend not restarted:** Kill uvicorn and restart
3. **Old session:** Create NEW quiz session (old ones won't have auto-advance enabled)
4. **Scheduler not running:** Check backend startup logs for "[SCHEDULER] Scheduler started"

---

**Test Time:** 5 minutes
**Expected Result:** Auto-advance works perfectly ✅
**Difficulty:** Easy (just pull and test!)

---

*Generated: 2025-11-16*
*Quick reference for testing auto-advance fixes*
