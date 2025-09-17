# 🛡️ Alert: 183 - Detect passwordless authentication

## ⚡ Quick Summary
• **Alert Type**: Alert
• **Rule ID**: 183
• **Severity**: Medium
• **Status**: Closed
• **Classification**: False Positive
• **Data Connector**: AD

## 📊 Incident Details
• **Incident Number**: 208306
• **Date**: 01-Jul-25 | **Time**: 07-01-2025 13:05
• **Shift**: Morning
• **Engineer**: Sarvesh
• **Handover Engineers**: Aman,Dhroovi,Saranya& Uday
• **Response Time**: 07-01-2025 13:12
• **Resolution Time**: 14 minutes
• **Resolution Timestamp**: 07-01-2025 13:19
• **SLA Breach Time**: 07-01-2025 17:05
• **VIP Users**: No

## 🔍 What Happened & Investigation
Triaging steps: IP : Clean, Closure comments :Observed events, checked sign in logs of users(obarkhordarian@arcutis.com,jfennewald@arcutis.com,nkolla@arcutis.com), clean IP, using registered devices and known apps nothing suspicious found , closing as a false positive

### Investigation Findings:
The investigation found that the passwordless authentication events were from known users (obarkhordarian@arcutis.com, jfennewald@arcutis.com, nkolla@arcutis.com) using registered devices and applications.  The IP addresses were clean. No suspicious activity was detected.

### Quality Assessment:
• **Quality Audit**: Pass
• **False Positive Reason**: Legitimate user
• **Justification**: Workspace not working

## 👨‍💻 Simple Investigation Steps (L1 Analyst Guide)

**Follow these steps in order when you get a similar alert:**

### Step 1: Initial Review
* **What to check first:**  The incident number, date, time, and involved users.  Check if any VIP users are involved.
* **Where to look for information:** The alert details in the ticketing system.
* **What questions to ask:** Are the users legitimate? Are the login locations and devices expected? Is the IP address known and safe?

### Step 2: Data Collection
* **What logs to check:** Check the sign-in logs for the users involved.  (This might involve using a specific KQL query, as mentioned in the procedure steps.)
* **Which users to investigate:** The users listed in the alert details (e.g., obarkhordarian@arcutis.com, jfennewald@arcutis.com, nkolla@arcutis.com).
* **What timeframes to review:** The timeframe around the reported alert time.

### Step 3: Analysis & Verification
* **How to verify if the threat is real:** Check if the users accessed any unusual applications or performed actions outside their normal behavior. Verify the IP addresses used for logins.
* **What patterns to look for:** Unusual login times, locations, or devices.  Multiple login attempts from the same user.
* **How to check IP reputation:** Use a tool like VirusTotal to check the reputation of any involved IP addresses.

### Step 4: Decision Making
* **When to mark as True Positive:** If the passwordless authentication involved unauthorized access to sensitive systems or applications, or if the user's activity is otherwise suspicious (unusual login location, device, time, etc.).
* **When to mark as False Positive:** If the authentication was from a known user, using a registered device and application, from a known safe IP address, and no suspicious activity is observed.
* **When to escalate to L2/L3:** If you are unsure about the legitimacy of the activity, if VIP users are involved, if multiple users are affected, or if you cannot determine true/false positive within the SLA time.

### Step 5: Documentation
* **What to document:** All steps taken during the investigation, findings (including IP reputation checks, user verification, and location analysis), and the final classification (True Positive or False Positive).
* **How to close the ticket:** Follow your organization's standard procedures for closing security alerts.
* **What comments to add:** A clear summary of your investigation, including the reasons for your classification.

## ⚡ Actions Taken & Results
• **Triaging Steps**: IP address was checked and found to be clean. Sign-in logs for the involved users were reviewed.
• **IP Reputation**: Clean
• **User Verification**: Users were confirmed as legitimate employees.
• **Location Analysis**: Not specified in the provided data.
• **Device Analysis**: Devices and applications used were registered and known.
• **MFA Status**: Not specified in the provided data.
• **Escalation**: No escalation was necessary.

## 🎯 Quick Reference for L1 Analysts

### ✅ Investigation Checklist:
- [ ] Check incident details and priority
- [ ] Review user accounts involved
- [ ] Verify IP addresses and locations
- [ ] Check for VIP users
- [ ] Analyze login patterns
- [ ] Review MFA status (if applicable)
- [ ] Document findings clearly

### 🚨 When to Escalate:
• If you are unsure about the legitimacy of the activity.
• If VIP users are involved and activity looks suspicious.
• If multiple users are affected simultaneously.
• If you cannot determine true/false positive within SLA time (14 minutes in this case).

### 📝 Common Tools & Queries:
• KQL queries for reviewing sign-in logs.
• VirusTotal for IP reputation checks.

### 💡 Pro Tips:
• Always check IP reputation first.
• Look for patterns in login times and locations.
• VIP users require extra attention.
• Document everything clearly for future reference.

## 🔧 Technical Details
• **Service Owner**: Sentinel
• **Rule Details**: Rule#183-Detect passwordless authentication.  Passwordless authentication may be due to a compromised account or privileged account.
• **File References**: Rule#183 01-Jul'25 (208306).xlsx, Rule#183 01-Jul'25 (208306)(Sheet1).csv
• **Ticket Numbers**: 208306


---
**Analysis Completeness**: This analysis includes ALL available information from the provided JSON context.