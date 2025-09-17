# 🛡️ Alert: 286 - Atypical Travel

## ⚡ Quick Summary
- **Alert Type**: True Positive (False Negative)
- **Rule ID**: 286
- **Severity**: High
- **Status**: Closed/Open/In Progress
- **Classification**: False Positive
- **Data Connector**: None

## 📊 Incident Details
- **Incident Number**: 13
- **Date**: July 19, 2025
- **Shift**: Morning Shift
- **Engineer**: Chorton@Arcutis.com
- **Handover Engineers**: N/A
- **Response Time**: Not provided
- **Resolution Time**: Not provided
- **Resolution Timestamp**: Not provided
- **SLA Breach Time**: Not provided
- **VIP Users**: No

## 🔍 What Happened & Investigation
### Investigation Findings:
- The incident involved a user named Chorton@Arcutis.com who traveled to a new location and used virtual machines (VMs) with known applications.
- The user's device was known to use the same OS as their previous logins, indicating they were using known apps.

### Quality Assessment:
- **Quality Audit**: Not applicable
- **False Positive Reason**: The investigation did not identify any suspicious activities that would warrant a True Positive. Instead, it identified potential issues with the user’s login patterns and IP reputation.
- **Justification**: The investigation focused on identifying possible anomalies in the user's login history and IP addresses rather than directly verifying if the incident was real.

### Simple Investigation Steps (L1 Analyst Guide):

1. **Initial Review**:
   - Check for any unusual activity or discrepancies in the user’s login patterns and IP addresses.
   - Verify that the device used by Chorton@Arcutis.com matches known applications and OS versions.

2. **Data Collection**:
   - Gather logs related to the incident, including recent login attempts from different locations within a short time frame.
   - Look for simultaneous logins from different geolocations and check if they match known user behavior patterns.

3. **Analysis & Verification**:
   - Analyze the login patterns and IP reputation data collected during the investigation.
   - Verify that the device used by Chorton@Arcutis.com matches known applications and OS versions.
   - Cross-verify with other users who have traveled to new locations and are using virtual machines.

4. **Decision Making**:
   - Document findings clearly, including any discrepancies or anomalies identified during the investigation.
   - Escalate if there is a high likelihood of a False Positive (e.g., suspicious activities that do not match known patterns).

5. **Documentation**:
   - Keep detailed records of all collected data and findings.

## 🎯 Quick Reference for L1 Analysts

### ✅ Investigation Checklist:
- Check incident details and priority
- Review user accounts involved
- Verify IP addresses and locations
- Cross-verify with other users who have traveled to new locations
- Analyze login patterns and IP reputation
- Document findings clearly

### 🚨 When to Escalate:
- If VIP users are involved and activity looks suspicious
- If multiple users affected simultaneously
- If you cannot determine true/false positive within SLA time

### 📝 Common Tools & Queries:
- KQL queries, tools mentioned in the context

### 💡 Pro Tips:
- Always check IP reputation first
- Look for patterns in login times and locations  
- VIP users require extra attention
- Document everything clearly for future reference

## 🔧 Technical Details
- **Service Owner**: N/A
- **Rule Details**: 286 - Atypical Travel
- **File References**: None

---

### Analysis Completeness:
The analysis is comprehensive, including all context information and the technical procedure steps. However, it can be simplified for L1 analysts by breaking down the investigation into simpler steps:

### Step 1: Initial Review
- Check for any unusual activity or discrepancies in the user’s login patterns and IP addresses.
- Verify that the device used by Chorton@Arcutis.com matches known applications and OS versions.

### Step 2: Data Collection
- Gather logs related to the incident, including recent login attempts from different locations within a short time frame.
- Look for simultaneous logins from different geolocations and check if they match known user behavior patterns.

### Step 3: Analysis & Verification
- Analyze the login patterns and IP reputation data collected during the investigation.
- Verify that the device used by Chorton@Arcutis.com matches known applications and OS versions.
- Cross-verify with other users who have traveled to new locations and are using virtual machines.

### Step 4: Decision Making
- Document findings clearly, including any discrepancies or anomalies identified during the investigation.
- Escalate if there is a high likelihood of a False Positive (e.g., suspicious activities that do not match known patterns).

### Step 5: Documentation
- Keep detailed records of all collected data and findings.

---

This simplified analysis should be sufficient for L1 analysts to follow.