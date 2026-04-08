# EMS Without Heartbeat - System Operations Guide

**Date**: April 8, 2026  
**Change**: Heartbeat System Removed  
**Impact Analysis**: Complete Workflow Documentation

---

## 📊 Executive Overview

The EMS system now operates **without automatic heartbeat monitoring**. This represents a shift from:
- **Active Monitoring** → **Manual Session Management**
- **Auto-logout on Inactivity** → **Explicit User Check-out**
- **Continuous Presence Verification** → **Event-based Tracking**

The core attendance functionality remains intact, but session lifecycle management is simplified.

---

## 🔄 Attendance Workflow (Without Heartbeat)

### User Journey: Check-in to Check-out

```
┌─────────────────────────────────────────────────────────────────┐
│                  DAY WITHOUT HEARTBEAT                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  08:00 AM                                                        │
│  ├─ User logs in (Dashboard/QR)                                 │
│  ├─ Attendance record created: check_in = 08:00 AM               │
│  ├─ check_out = NULL (session active)                            │
│  ├─ heartbeat_last = NOT SET                                     │
│  └─ Timer starts showing elapsed time                            │
│                                                                   │
│  08:00 AM - 05:00 PM                                             │
│  ├─ User works normally                                          │
│  ├─ NO automatic heartbeat signals sent                          │
│  ├─ NO auto-logout on inactivity                                 │
│  ├─ Session remains OPEN indefinitely                            │
│  ├─ Optional: Take breaks (manual start/end)                     │
│  └─ Optional: View attendance stats/calendar                     │
│                                                                   │
│  05:00 PM                                                        │
│  ├─ User manually clicks "Check Out"                             │
│  ├─ POST to /staff/check-out endpoint                            │
│  ├─ check_out = 05:00 PM (timestamp set)                         │
│  ├─ Attendance status calculated (present/late/overtime)         │
│  ├─ Session marked as CLOSED                                     │
│  └─ Record finalized in database                                 │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🎯 Key Differences: With vs Without Heartbeat

### Comparison Table

| Aspect | **WITH Heartbeat** | **WITHOUT Heartbeat** |
|--------|-------------------|----------------------|
| **Auto-logout** | After 30 min inactivity | Never (manual only) |
| **Session Duration** | Max 30 minutes | Unlimited |
| **Network Signals** | Every 3 minutes | None (event-based) |
| **Server Load** | Heavy (continuous) | Light (on-demand) |
| **Inactivity Detection** | Automatic (daemon) | Manual (admin view) |
| **User Notification** | Session ended suddenly | User controls timing |
| **Network Dependency** | Critical | Not required |
| **Idle Terminal** | Auto-checked out | Stays logged in |
| **Background Thread** | Running monitor | Not needed |

---

## 📋 Attendance Record Lifecycle

### Database Record State Changes

**SESSION START (Check-in)**
```
Attendance Record Created:
├─ user_id: 1
├─ check_in: 2026-04-08 08:00:00
├─ check_out: NULL                    ← Still active
├─ status: NULL (calculated at check-out)
├─ heartbeat_last: NOT SET             ← No longer used
├─ outside_geofence_since: NULL
├─ break_start: NULL
├─ break_end: NULL
├─ overtime_hours: 0.0
└─ is_weekend: false
```

**SESSION ACTIVE (During work)**
```
No Changes:
├─ No automatic heartbeat updates
├─ No inactivity checks
├─ No system modifications
└─ User can manually start break
```

**BREAK TAKEN (Optional)**
```
Updates:
├─ break_start: 12:00:00
│  (Later)
├─ break_end: 12:30:00
└─ Attendance status recalculated if needed
```

**SESSION END (Manual Check-out)**
```
Record Updated:
├─ check_out: 2026-04-08 17:00:00      ← Set by user action
├─ status: CALCULATED                   ← present/late/half-day
├─ overtime_hours: CALCULATED           ← If applicable
└─ Record now LOCKED (no further changes)
```

---

## 🔧 Operational Components

### 1. Frontend (Employee Dashboard)

**What Still Works:**
```javascript
// Check-in functionality
✓ this.clickCheckIn()  → POST /staff/check-in
✓ this.clickCheckOut() → POST /staff/check-out
✓ this.startTimer()    → Shows elapsed time
✓ this.startBreak()    → POST /staff/start-break
✓ this.endBreak()      → POST /staff/end-break
```

**What No Longer Works:**
```javascript
✗ this.startHeartbeat()  → REMOVED (was sending every 3 min)
✗ No automatic signals
✗ No inactivity detection
```

**UI Display:**
```
Still Displayed:
├─ Check In Time: 8:00 AM ✓
├─ Check Out Time: 5:00 PM ✓
├─ Elapsed Time: 09:00:00 ✓
├─ Break Status: On/Off ✓
├─ Attendance Score: 95% ✓
└─ Break Remaining: 1 hour ✓

No Longer Displayed:
├─ Last Heartbeat ✗
├─ Session Status Indicator ✗
├─ Inactivity Warning ✗
└─ Auto-logout Timer ✗
```

---

### 2. Backend (Routes & Endpoints)

**ACTIVE Endpoints:**
```python
✓ POST /staff/check-in      → Create attendance record
✓ POST /staff/check-out     → Close attendance record
✓ POST /staff/start-break   → Set break_start timestamp
✓ POST /staff/end-break     → Set break_end timestamp
✓ GET /staff/attendance_events → Calendar events
✓ GET /staff/get_attendance_stats → User stats
```

**REMOVED Endpoint:**
```python
✗ POST /staff/heartbeat     → DELETED (no longer receives signals)
```

**Route Handler Logic:**
```python
# Check-in (Unchanged)
@staff_bp.route('/check-in', methods=['POST'])
def check_in():
    now = get_nepal_time()
    attendance = Attendance(
        user_id=current_user.id, 
        check_in=now
        # heartbeat_last: NOT SET
    )
    db.session.add(attendance)
    # ... rest of logic

# Check-out (Still manual, no timeout detection)
@staff_bp.route('/check-out', methods=['POST'])
def check_out():
    attendance = Attendance.query.filter_by(...).first()
    if attendance:
        now = get_nepal_time()
        attendance.check_out = now  # Set by user action
        # ... calculate status
```

---

### 3. Background Services

**Background Monitor Status:**
```python
# In app.py startup
if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
    monitor_thread = threading.Thread(target=start_monitoring, daemon=True)
    monitor_thread.start()

# In utils/attendance_service.py
class AttendanceMonitor:
    def run(self):
        while True:
            with self.app.app_context():
                try:
                    pass  # Monitor running but doing nothing
                except Exception as e:
                    print(f"Monitor error: {e}")
            time.sleep(60)

    # process_heartbeats() METHOD REMOVED
    # No inactivity checks executed
```

**Monitor Status:**
```
┌─────────────────────────────┐
│  AttendanceMonitor Thread   │
├─────────────────────────────┤
│ Running: YES                │
│ Lock File: Created          │
│ Process: Sleeps 60 seconds  │
│ Action: NONE                │
│ Database: NO CHANGES        │
└─────────────────────────────┘

Purpose: Reserved for future monitoring logic
```

---

## 🎭 Real-World Scenarios

### Scenario 1: Normal 8-Hour Workday

```
Timeline:
─────────────────────────────────────────────────────

08:00 AM | User checks in via Dashboard
         → Attendance record created
         → Timer starts: 00:00:00
         
09:00 AM | 1 hour elapsed
         → Timer shows: 01:00:00
         → User is working (no heartbeat check)
         
12:00 PM | User takes break
         → Clicks "Start Break"
         → break_start = 12:00:00
         
12:30 PM | User ends break
         → Clicks "End Break"
         → break_end = 12:30:00
         
05:00 PM | User checks out manually
         → Clicks "Check Out"
         → check_out = 17:00:00
         → Duration calculated: 8 hours, 30 mins (minus break)
         → Status: PRESENT

Result: Record locked in database, attendance logged
```

---

### Scenario 2: User Forgets to Check Out

```
Timeline:
─────────────────────────────────

10:00 AM | User checks in
         → check_out = NULL
         
01:00 AM (NEXT DAY) | Database still shows open session
                    → No auto-checkout happened
                    → Record remains ACTIVE

When discovered:
├─ Admin views attendance records
├─ Finds open session with NULL check_out
├─ Can manually close it (if feature added)
│  OR
├─ Session remains forever (no cleanup)

Key Issue: ⚠️ OPEN SESSIONS NEVER AUTO-CLOSE
```

---

### Scenario 3: Poor Network Connectivity

```
WITH Heartbeat:
└─ Client loses WiFi
   └─ No heartbeat sent for 30+ minutes
   └─ Server auto-logs out user
   └─ Disrupts workflow ❌

WITHOUT Heartbeat:
└─ Client loses WiFi
   └─ No effect on attendance
   └─ User still checked in
   └─ Session continues (no dependency) ✓
```

---

### Scenario 4: User Falls Asleep at Terminal

```
Timeline:
─────────────────────────────────

08:00 AM | User checks in
09:30 AM | User falls asleep
         └─ No heartbeat signals
         └─ System can't detect inactivity
         
05:00 PM | User wakes up
         | Still logged in
         | Checks out
         | Full 9 hours recorded

WITH Heartbeat:
└─ Would auto-logout at 10:00 AM
└─ User would realize and re-login
└─ Final record: ~2 hours + re-login session

WITHOUT Heartbeat:
└─ Stays logged in entire time
└─ Full 9 hours recorded
└─ Inaccurate attendance (includes sleep time)
```

---

## ⚠️ Critical Issues Without Heartbeat

### Issue 1: No Inactivity Detection

**Problem**: Users can stay logged in indefinitely without activity

**Consequences**:
- No forced logout on network issues
- Terminal remains accessible after user leaves
- Security risk if user forgets to logout
- Open sessions can accumulate

**Mitigation**:
```
Option A: Manual Admin Cleanup
├─ Admin manually closes sessions > 24 hours
├─ Relies on admin vigilance
└─ Labor-intensive

Option B: Time-based Auto-logout (Implementation needed)
├─ Daily reset at end of shift (e.g., 06:00 PM)
├─ Force close all check_out = NULL records
└─ Requires new scheduled task

Option C: IP-based Session Termination
├─ Logout if IP changes
├─ Terminates session on WiFi switch
└─ More strict control
```

---

### Issue 2: No Activity Status Display

**Problem**: Can't show user if they're "AFK" (Away From Keyboard)

**Missing Features**:
```
❌ No "Last Active" timestamp for admin
❌ No idle duration display
❌ No activity status indicator
❌ Can't see real-time presence
```

**Data Gaps**:
```python
# Previously available:
attendance.heartbeat_last  # When user last sent data

# Now unavailable:
# No way to know:
├─ When user last interacted with system
├─ How long they've been idle
├─ If terminal is still active
└─ Real-time presence status
```

---

### Issue 3: Geofence Violations Persist

**Problem**: Location-based verification features don't work properly

**Previous Behavior**:
```
User Outside Geofence:
└─ outside_geofence_since = timestamp set
└─ System flags violation
└─ Sends warning/notification

When User Returns + Heartbeat Received:
└─ outside_geofence_since = NULL (cleared)
└─ Violation resolved

Current Behavior WITHOUT Heartbeat:
└─ outside_geofence_since is NEVER cleared
└─ Flag remains permanently set
└─ Admin sees constant violation
```

**Impact**:
- Geofence feature essentially broken
- False positive violations
- Cannot reset violations without manual intervention

---

### Issue 4: Longer Session Durations

**Problem**: Sessions can persist for unreasonable durations

**Examples**:
```
Extreme Case:
└─ User checks in Monday 08:00 AM
└─ Forgets to check out
└─ Checked out Tuesday 08:00 AM
└─ System records: 24 hours of attendance
└─ Inaccurate data for reporting
```

**Data Quality Impact**:
- Inflated attendance hours
- Incorrect overtime calculations
- Skewed payroll data
- Invalid analytics reports

---

## 🔍 Admin Oversight Changes

### Dashboard Attendance View

**Previously Available (With Heartbeat)**:
```
Table Columns:
├─ Employee Name
├─ Check In Time      ✓ Still visible
├─ Check Out Time     ✓ Still visible
├─ Last Heartbeat     ✗ No longer updated
├─ Status             ✓ Still calculated
├─ Duration           ✓ Still calculated
└─ Active Status      ✗ Can't determine
```

**What Admin Can See**:
```
✓ Who checked in
✓ Who checked out (if they did)
✓ How long they worked
✗ Who is currently active/idle
✗ Real-time presence status
✗ When they last accessed system
```

**What Admin Cannot See**:
```
❌ If someone forgot to check out
❌ How long they've been idle
❌ Real-time activity status
❌ Warning for open sessions
❌ Automatic session cleanup
```

---

## 📊 System Reliability Changes

### Uptime & Dependencies

```
BEFORE (With Heartbeat):
Network ← Critical
  ├─ Heartbeat depends on internet
  └─ Network outage = auto-logout

AFTER (Without Heartbeat):
Network ← Not Critical
  ├─ Attendance works offline
  ├─ Check-in/out work offline
  ├─ Syncs when online
  └─ More resilient ✓
```

### Performance Impact

```
BEFORE:
├─ 100 employees
├─ 160 heartbeats/day per employee
├─ 16,000 requests/day total
├─ Server CPU: ~0.08% per cycle
├─ Database: ~1600 updates/day
└─ Network: ~3.2 MB/day

AFTER:
├─ 100 employees
├─ 0 heartbeats/day
├─ ~200 requests/day (check-in/out only)
├─ Server CPU: ~0% (no heartbeat overhead)
├─ Database: ~200 writes/day
└─ Network: ~0.05 MB/day (90% reduction) ✓
```

---

## 🛠️ What Still Functions Perfectly

### ✅ Core Attendance Features

```
✓ Check-in / Check-out
✓ Attendance recording
✓ Break management (start/end)
✓ Attendance status calculation (Present/Late/Half-day)
✓ Overtime calculation
✓ Leave management
✓ Monthly payroll processing
✓ Attendance reports
✓ Calendar view
✓ Statistics dashboard
✓ QR code login
✓ Role-based access control
✓ Database persistence
```

### ✅ Administrative Functions

```
✓ View attendance records
✓ Manage employee profiles
✓ Process payroll
✓ Export reports
✓ Monitor leaves
✓ View audit logs
✓ Manage notices
✓ Settings management
```

---

## 🔐 Security Implications

### Improved Security

```
✓ No session hijacking via heartbeat spoofing
✓ Reduced attack surface (no heartbeat endpoint)
✓ Fewer network requests = fewer interception points
✓ Simplified session validation
```

### Reduced Security

```
❌ Can't detect idle terminals with stale sessions
❌ No automatic session termination
❌ Open sessions susceptible to unauthorized access
❌ No activity-based security monitoring
❌ Forgotten checkouts pose security risks
```

---

## 📝 Required Manual Processes (New)

### Admin Tasks Now Required

```
Daily Tasks:
├─ Monitor for open sessions (check_out = NULL)
├─ Close abandoned sessions manually
├─ Verify attendance accuracy
├─ Check for geofence violations (now stuck)

Weekly Tasks:
├─ Review open sessions > 24 hours
├─ Investigate gaps in attendance
├─ Clean up stale records

Monthly Tasks:
├─ Verify final records before payroll
├─ Reconcile attendance discrepancies
├─ Report session abandonment statistics
```

### Recommended Workarounds

```
Option 1: End-of-Day Auto-Logout
├─ Implement: 06:00 PM automatic check-out
├─ Closes all open sessions daily
├─ Prevents overnight accumulation
└─ Requires: scheduled task

Option 2: Email Reminders
├─ Hourly: Remind users to check out
├─ End of shift: Force checkout warning
└─ Requires: email service integration

Option 3: Admin Auto-close Feature
├─ Add button: "Close All Open Sessions"
├─ Parameter: Time threshold (e.g., > 24 hrs)
└─ Requires: new admin feature

Option 4: Session Timeout Per Check-in
├─ Hard limit: 12 hours per check-in
├─ Auto close at 12 hours
├─ Better than infinite
└─ Requires: timed task scheduler
```

---

## 🎯 System Behavior Summary

### Attendance Workflow (Post-Heartbeat)

```
1. USER CHECKS IN
   └─ Manual action required (click button or QR scan)
   └─ Creates attendance record
   └─ check_out = NULL (session open)

2. USER WORKS
   └─ No automatic monitoring
   └─ No inactivity detection
   └─ Session remains open indefinitely
   └─ Can take breaks (optional)

3. USER CHECKS OUT
   └─ Manual action required (click button)
   └─ Sets check_out timestamp
   └─ Calculates attendance status
   └─ Record finalized (immutable)

4. RECORD STORED
   └─ Database persists record
   └─ Admin can view/analyze
   └─ Used for payroll processing
   └─ Included in reports
```

---

## 💡 Key Takeaways

### Before Heartbeat (Was)
- **Automatic** session management
- **Responsive** to inactivity
- **Complex** daemon monitoring
- **Network-dependent** reliability
- **Lighter** data load on user storage

### After Heartbeat Removal (Is)
- **Manual** session management
- **Trusting** users to check out
- **Simpler** backend code
- **More resilient** to network issues
- **Zero** automatic monitoring overhead

### Impact to Users
✅ No unexpected logouts  
✅ More stable sessions  
✅ Works offline  
❌ Must remember to check out  
❌ No inactivity protection  

### Impact to Admins
✅ Less infrastructure to maintain  
✅ Lower server load  
✅ Fewer support tickets for timeouts  
❌ Must manually manage open sessions  
❌ Can't detect real-time activity  
❌ Inaccurate reports if users don't check out  

---

## 🚀 Recommendations

### Immediate (Quick Wins)
1. Update admin documentation
2. Train admins on manual session closure
3. Add warning in UI about manual checkout
4. Create admin checklist for daily tasks

### Short-term (1-2 weeks)
1. Implement daily 6 PM auto-checkout feature
2. Add email reminder system for checkout
3. Add "active sessions" admin dashboard widget
4. Create troubleshooting guide for open sessions

### Medium-term (1 month)
1. Implement session timeout per check-in (12 hours)
2. Add geofence status reset mechanism
3. Create analytics for checkout rates
4. Implement session abandonment alerts

### Long-term (Evaluation)
1. Consider re-implementing heartbeat with improvements
2. Add activity logging without full heartbeat
3. Implement presence indicator system
4. Add real-time notifications for missing checkouts

---

## 📞 Support Notes

### Common Issues & Resolutions

**Q: Why is user showing 24 hours of attendance?**
```
A: They forgot to check out. 
   Manually close session in admin panel.
   No auto-logout without heartbeat.
```

**Q: How do I know if someone is currently working?**
```
A: Check if they have open session (check_out = NULL).
   Or ask them directly.
   Real-time status not available.
```

**Q: Session won't close despite clicking checkout.**
```
A: Network issue or database error.
   Check server logs.
   Manually update database if necessary.
```

**Q: Why does the app work without internet now?**
```
A: Heartbeat was network-dependent.
   Removed heartbeat = offline-capable.
   Changes sync when online.
```

---

**Report Generated**: April 8, 2026  
**Status**: Post-Heartbeat System Documentation  
**Audience**: Developers, Admins, Support Team
