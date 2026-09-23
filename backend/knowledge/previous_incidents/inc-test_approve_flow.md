# Historical Incident: INC-TEST_APPROVE_FLOW

## Problem Description
High connection count and timeout on orders-api

## Root Cause
Database connection pool exhaustion introduced by recent deployment

## Explanation
The only concrete change preceding the outage is deployment DEP-GH-BD914E3 at 2026-09-23T18:36:45Z, matching the temporal pattern of past incidents where a deployment leaked DB connections and caused timeouts. Metrics show EC2 CPU at 0.77% (no compute pressure) and no RDS/ALB data, indicating the problem is not CPU or load‑balancer saturation but likely hidden in the application layer. Historical memory of similar incidents (INC-E2E_APPROVAL_TEST, INC-TEST-1001) links deployments to DB connection pool failures. Although direct DB metrics are missing, the convergence of a recent code change, low compute usage, and prior patterns points to a connection‑pool exhaustion as the root cause.

## Fix Applied
rollback_deployment

## Result
Resolved and Verified successfully.
