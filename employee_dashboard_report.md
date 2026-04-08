# 👔 Employee Dashboard Report (V2)

This report detail the specific features and interface elements available to **Full-time Employees** in the EMS portal.

---

## 🏗️ 1. Navigation & Access
*   **Breadcrumb**: `Staff Dashboard > Employee`
*   **Primary Menu**: `Dashboard`, `My Profile`, `My Queries`, `Leaves`, `Payslips`.

---

## ⚡ 2. The Command Center (Attendance Hub)
*   **Attendance Clock**: Real-time ticker showing the duration of the current shift.
*   **Check-in/Out Logic**:
    *   **Emerald**: Logged in and active.
    *   **Rose**: Session end confirmation.
*   **Break Management**: Toggle between `Take Break` and `End Break` with automatic timer pausing logic.
*   **Heartbeat**: Background sync to preserve the session for exactly 180 seconds between updates.

---

## 📈 3. Employee-Specific Insight Grid
*   **Attendance Score**: Live percentage of present days in the current month.
*   **Leave Balance**: Instant O(1) day counter of remaining paid leaves.
*   **Monthly Base Salary**: Displays the fixed salary amount from the profile.
*   **💰 Live Overtime Estimator**:
    *   Calculates overtime payout in real-time after the 8th work hour.
    *   Displays the hourly rate (e.g., Rs. 500/hr) for transparency.

---

## 🗓️ 4. Activity & Communications
*   **FullCalendar Log**: Monthly view showing `Present`, `Absent`, and `Half-day` statuses.
*   **Absent Saturday Legend**: High-contrast pink highlight for Saturdays without attendance records.
*   **Notice Board**: Feed for company-wide internal memos.

---

## 🛡️ 5. Security Hub
*   **Boot ID Protection**: Ensures session integrity after server restarts.
*   **QR Security Badge**: Downloadable digital ID for scanning at office terminals.
