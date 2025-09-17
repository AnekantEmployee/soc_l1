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
- **IP Reputation Status**: Not found in the provided context.
- **Locations**: Not found in the provided context.
- **MFA Status**: Not found in the provided context.
- **Sign In Logs**: Not found in the provided context.

## Investigation Procedure Steps
1. **Triaging Steps:**
   - IP : Clean
   - Closure Comments: Observed events, checked sign in logs of users(obarkhordarian@arcutis.com,jfennewald@arcutis.com,nkolla@arcutis.com), clean IP, using registered devices and known apps nothing suspicious found , closing as a false positive

2. **Resolution Time:** 14 minutes

3. **Reason for False Positive:**
   - The incident was detected due to the use of passwordless authentication methods, which may be compromised or used by unauthorized users.

## Remediation Actions
- **Action Taken**: No specific remediation steps are provided in the context.
- **Action Not Taken**: Not applicable as no remediation actions were mentioned.

**DATA EXTRACTION RULES:**
- Extract rule_id, alert_name from extracted_rule_info
- Get incident details from tracker_data section
- Use resolver_comments for investigation findings
- Extract procedure_steps from rulebook_records

## FORBIDDEN: 
- Do not invent or assume any information
- Do not mix information from different rules
- Do not add procedural steps not in the context
- Do not speculate on missing information
**OUTPUT VALIDATION:**
Ensure your response:
1. Follows the exact markdown structure specified above
2. Uses only information from the provided JSON context
3. Includes specific data points like incident numbers, dates, times
4. Maintains professional SOC terminology
5. Clearly indicates when information is missing from context
6. Consistently uses "Not found in provided context" where applicable