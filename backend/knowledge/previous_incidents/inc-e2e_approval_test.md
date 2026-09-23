# Historical Incident: INC-E2E_APPROVAL_TEST

## Problem Description
Container crashing repeatedly due to OOM killer

## Root Cause
Memory exhaustion due to unreleased database connections introduced in recent deployment (DEP‑184), causing OOM kills

## Explanation
Both investigators correctly identify that the container is being terminated by the OOM killer, but the runbook context adds a concrete trigger: the latest deployment (DEP‑184) changed database and connection‑pool code, leading to unreleased sessions and SQLAlchemy QueuePool timeouts. This pool exhaustion creates a large number of blocked threads that consume memory, ultimately exceeding the container’s cgroup limit and invoking the OOM killer. Investigator A pinpoints the recent code change, while Investigator B correctly notes that memory overload is the immediate failure mode. Together they explain the symptom and its root cause.

## Fix Applied
rollback_deployment

## Result
Resolved and Verified successfully.
