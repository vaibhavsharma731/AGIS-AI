# Runbook: High Memory Utilization & Memory Leaks

## Symptoms
- System memory utilization steadily climbs to 90%+ over time.
- Containers crash with `OOM-Killer` or `SIGKILL (signal 9)`.
- Logs show `MemoryError: Unable to allocate array buffer`.

## Root Causes
1. **Unbounded In-Memory Caches**: Storing large query results in global dictionaries without eviction policies (TTL/LRU).
2. **Unclosed File/Socket Handles**: Accumulation of file streams or socket handles in memory.

## Recommended Remediation
1. **Rollback Deployment**: Revert the commit introducing the unbounded memory cache.
2. **Restart Service Instances**: Instantly releases leaked RAM to stabilize the service while fixing root cause.
