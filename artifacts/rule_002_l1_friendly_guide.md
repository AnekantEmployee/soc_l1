# 🛡️ Alert: 002 - Attempt to bypass conditional access rule in Microsoft Entra ID

## ⚡ Quick Summary
• **Alert Type**: Alert
• **Rule ID**: 002
• **Severity**: Low
• **Status**: Closed
• **Classification**: False Positive
• **Data Connector**: AD

## 📊 Incident Details
• **Incident Number**: 208307
• **Date**: 01-Jul-25 | **Time**: 07-01-2025 13:11
• **Shift**: Morning
• **Engineer**: Sarvesh
• **Handover Engineers**: Aman, Dhroovi, Saranya & Uday
• **Response Time**: 07-01-2025 13:12
• **Resolution Time**: 12 minutes
• **Resolution Timestamp**: 07-01-2025 13:23
• **SLA Breach Time**: 07-01-2025 21:11 (Resolved before breach)
• **VIP Users**: Yes

## 🔍 What Happened & Investigation
Triaging steps: IP : Clean, Closure comments : Observed the events , checked the logs for the users , all failed attempts were seen , known clean IPs were seen. Location US,IN,MX & MA, guest MFA enabled for users nothing suspicious found.

### Investigation Findings:
The investigation revealed that the alert was triggered by legitimate users experiencing workspace issues.  The IPs involved were known clean IPs, and the locations (US, IN, MX, MA) were not unusual.  Guest MFA was enabled for the users. No malicious activity was detected.

### Quality Assessment:
• **Quality Audit**: Pass
• **False Positive Reason**: Legitimate user
• **Justification**: Workspace not working

## 👨‍💻 Simple Investigation Steps (L1 Analyst Guide)

**Follow these steps in order when you get a similar alert:**

### Step 1: Initial Review
* **What to check first:**  The incident number (208307 in this case), the reported time (7/1/2025 13:11), and whether VIP users are involved (Yes, in this case).
* **Where to look for information:** The incident details in the alert itself.
* **What questions to ask:**  Is this a VIP user? What time did the event occur?  What is the incident number?

### Step 2: Data Collection
* **What logs to check:**  Check the audit sign-in logs and location logs for the users involved.
* **Which users to investigate:**  The users mentioned in the incident details.
* **What timeframes to review:** The timeframe around the reported time (7/1/2025 13:11).

### Step 3: Analysis & Verification
* **How to verify if the threat is real:** Check the IP addresses for malicious activity using an IP reputation tool. Review user login locations to see if they match known locations. Examine login attempts for patterns of failure.
* **What patterns to look for:** Unusual login locations, multiple failed login attempts from the same IP, logins outside of normal working hours.
* **How to check IP reputation:** Use a reputable IP reputation database or tool.

### Step 4: Decision Making
* **When to mark as True Positive:** If you find malicious IPs, unusual login locations, or suspicious login patterns.
* **When to mark as False Positive:** If the IPs are clean, locations are expected, and there's no evidence of malicious activity (like in this case).
* **When to escalate to L2/L3:** If you are unsure about the nature of the activity, if VIP users are involved and the activity is suspicious, if multiple users are affected simultaneously, or if you cannot determine true/false positive within the SLA time.

### Step 5: Documentation
* **What to document:** All steps taken during the investigation, findings (IP addresses, locations, user details), and the reason for classifying the alert as a true or false positive.
* **How to close the ticket:** Follow standard procedures for closing tickets in your system.
* **What comments to add:** A clear summary of your investigation and findings, including any actions taken.


## ⚡ Actions Taken & Results
• **Triaging Steps**: IP reputation checked, user logs reviewed, login attempts analyzed.
• **IP Reputation**: IPs were identified as clean.
• **User Verification:** Users were confirmed as legitimate.
• **Location Analysis**: Login locations were consistent with expected locations.
• **Device Analysis**: No specific device information was provided in this incident.
• **MFA Status**: Guest MFA was enabled for the users.
• **Escalation**: No escalation was necessary.

## 🎯 Quick Reference for L1 Analysts

### ✅ Investigation Checklist:
- [ ] Check incident details and priority
- [ ] Review user accounts involved
- [ ] Verify IP addresses and locations using an IP reputation tool
- [ ] Check for VIP users
- [ ] Analyze login patterns (frequency, time, location)
- [ ] Review MFA status
- [ ] Document findings clearly

### 🚨 When to Escalate:
• If you find suspicious activity that you're unsure about.
• If VIP users are involved and activity looks suspicious.
• If multiple users are affected simultaneously.
• If you cannot determine true/false positive within SLA time.

### 📝 Common Tools & Queries:
KQL queries to check user login locations and IP addresses.  IP reputation tools.

### 💡 Pro Tips:
• Always check IP reputation first.
• Look for patterns in login times and locations.
• VIP users require extra attention.
• Document everything clearly for future reference.


## 🔧 Technical Details
• **Service Owner**: Sentinel
• **Rule Details**: Rule#002-Attempt to bypass conditional access rule in Microsoft Entra ID.  (More detailed rule information may be available in `direct_file_rule_002`)
• **File References**: Rule#002 -01-Jul-25 (208307).xlsx
• **Ticket Numbers**: 208307


---
**Analysis Completeness**: This analysis includes ALL available information from the provided JSON context.