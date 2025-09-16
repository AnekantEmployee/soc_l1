# Rule 183 - Detect passwordless authentication

## Key Information
- **Rule ID**: 183
- **Alert Name**: Detect passwordless authentication
- **Severity**: Medium
- **Category**: False Positive

## Recent Incident Summary
- **Incident Number**: 208306
- **Date**: July 1, 2025
- **Priority**: Medium
- **Status**: Closed
- **Engineer**: Sarvesh
- **Resolution Time**: 14 minutes
- **Classification**: False Positive

## Investigation Findings
- **IP Reputation Status**: No IP reputation status is provided.
- **Locations**: Not specified in the context.
- **MFA Status**: MFA status is not relevant to this incident.

## Investigation Procedure Steps
1. **Triaging Steps:**
   - **IP Clean**: Check if there are any suspicious or compromised IPs involved.
   - **Closure Comments**: Review and comment on observed events, check sign-in logs of users with the provided credentials (obarkhordarian@arcutis.com, jfennewald@arcutis.com, nkolla@arcutis.com).
   - **Clean IP**: Use registered devices and known apps to clean the compromised IP.
   - **Using Registered Devices and Known Apps**: Check if there are any applications without sign-in attempts.

2. **Verification of Application Sign-In Attempts:**
   - Run a KQL query to verify the application sign-in attempts.
   - Collect basic information like usernames, app names, user agents, time stamps, etc., from the logs.

3. **User Confirmation and User Account Details:**
   - If no critical applications are found without password, consider this as a False Positive.
   - Inform IT team to investigate further if any critical applications are present.

4. **Run AD Logs (Sign-in Logs):**
   - Ensure that the passwordless authentication method used is legitimate (e.g., biometrics, hardware tokens).
   - If there are critical applications without password, reach out IT for setting MFA.

5. **User Account Details:**
   - Collect basic user information like usernames, app names, user agents, time stamps, etc.
   - Inform IT team if any critical applications are found without password.

## Remediation Actions
- **Run AD Logs (Sign-in Logs)**:
  - Ensure that the passwordless authentication method used is legitimate (e.g., biometrics, hardware tokens).
  - If there are critical applications without password, reach out IT for setting MFA.
  
- **User Account Details**:
  - Collect basic user information like usernames, app names, user agents, time stamps, etc.
  - Inform IT team if any critical applications are found without password.

## Additional Information
- **Attachments**: Not applicable in this context.
- **Attachments**: Not applicable in this context.
- **Attachments**: Not applicable in this context.
- **Attachments**: Not applicable in this context.
- **Attachments**: Not applicable in this context.
- **Attachments**: Not applicable in this context.
- **Attachments**: Not applicable in this context.

This analysis focuses on the detection of passwordless authentication and provides a structured response following the provided guidelines.