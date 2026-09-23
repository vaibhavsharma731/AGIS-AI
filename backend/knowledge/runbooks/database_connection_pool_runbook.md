# Runbook: Database Connection Pool Exhaustion

## Symptoms
- API response latency spikes significantly (e.g. > 3000ms).
- High HTTP 500 Error rates on API endpoints.
- Logs contain `QueuePool limit overflow`, `sqlalchemy.exc.TimeoutError`, or `Database connection pool exhausted`.
- CPU utilization is high due to thread contention waiting for DB sockets.

## Root Causes
1. **Unclosed DB Connections**: Recent code changes that open database sessions without proper context managers (`with Session()`) or missing `session.close()`.
2. **Long-running Queries**: Unindexed queries blocking pool slots.
3. **Traffic Spike**: Request volume exceeding configured pool size limits.

## Diagnostic Steps
1. Check active DB connections metric against max pool size (e.g. 100/100).
2. Inspect recent deployments to see if `database.py` or connection handling code was modified.
3. Check error logs for connection timeout exceptions.

## Recommended Remediation
1. **Rollback Recent Deployment**: If a code deployment occurred within 30 minutes before the incident, roll back to the previous stable release.
2. **Restart Web Service Containers**: Temporary mitigation to release hanging connection sockets.
3. **Emergency Pool Scale**: Increase `POOL_SIZE` in environment variables as a temporary patch.
