# Historical Incident: INC-TEST-1001

## Problem Description
API response time spiked to 4.8s

## Root Cause
Database connection pool misconfiguration and session leak introduced in Deployment DEP-184

## Explanation
Investigator A correctly identified the primary root cause: Deployment DEP-184 modified backend session lifecycle and pool timeout settings in backend/database.py and backend/connection_pool.py, leading to unclosed sessions and pool exhaustion. Investigator B focused on symptoms (high CPU utilization and maxed DB connection limits), whereas the runbook and historical incident INC-TEST-1001 clarify that CPU saturation was a downstream symptom caused by application thread contention waiting for DB connection sockets.

## Fix Applied
rollback_deployment

## Result
Resolved and Verified successfully.
