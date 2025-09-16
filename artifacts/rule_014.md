# Rule 014 - User Assigned Privileged Role

## Key Information
- **Rule ID**: 014
- **Severity**: High
- **Category**: Security

## Recent Incident Summary
- **Incident Number**: 208309
- **Date**: July 1, 2025
- **Priority**: High
- **Status**: Closed
- **Engineer**: Saranya
- **Resolution Time**: 4 minutes
- **Classification**: FP

## Investigation Findings
- **Incident Details**: A user has been assigned a privileged role. The user is not authorized to access the system.
- **Investigation Steps**:
  - Gather details of all users (incident number: 208309)
  - Check alert details for unusual sign-in patterns by the assigned user
  - Verify if the assigning user had legitimate access and permissions

## Investigation Procedure Steps
1. **Gather Details**: Check incident number, date, time.
2. **Check Alert Details**: Look for unusual sign-in patterns by the assigned user.
3. **Verify Role Sensitivity**: Determine if the assigned role is high-risk (e.g., Global Admin).
4. **Review Sign-In Logs**: Check for unusual sign-in patterns by the assigned user.

## Remediation Actions
- **Escalate to L3/IT**: If suspicious, escalate to L3/IT for investigation.
- **Reset Account and MFA Tokens**: If True Positive (TP) scenarios are identified, reset the account and revoke MFA tokens.
- **Temporary Disable Account**: If False Positive (FP) scenarios are identified, temporarily disable the account.

## DATA EXTRACTION RULES
- Extract rule_id: 014
- Get incident details from tracker_data section
- Use resolver_comments for investigation findings

**DATA EXTRACTION RULES:**
- Extract rule_id: 014
- Get incident details from tracker_data section
- Use resolver_comments for investigation findings