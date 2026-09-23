"""
backend/app/services/aws_service.py

Service for querying real server metrics and logs from AWS CloudWatch using boto3.
Includes graceful error handling and fallback when credentials/boto3 are absent.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from backend.app.config import settings

logger = logging.getLogger(__name__)

def get_boto3_client(service_name: str, access_key: str = "", secret_key: str = "", region: str = ""):
    """Dynamically creates a boto3 client if credentials and library exist."""
    try:
        import boto3
        target_region = region or settings.AWS_REGION or "us-east-1"
        kwargs = {"region_name": target_region}
        ak = access_key or settings.AWS_ACCESS_KEY_ID
        sk = secret_key or settings.AWS_SECRET_ACCESS_KEY
        if ak and sk:
            kwargs["aws_access_key_id"] = ak
            kwargs["aws_secret_access_key"] = sk
        else:
            return None

        return boto3.client(service_name, **kwargs)
    except ImportError:
        logger.warning("[AWS Service] 'boto3' module is not installed.")
        return None
    except Exception as e:
        logger.error(f"[AWS Service] Failed to initialize boto3 client for {service_name}: {e}")
        return None

def test_aws_connection(access_key: str = "", secret_key: str = "", region: str = "") -> Dict[str, Any]:
    """Tests connectivity with AWS credentials using STS or CloudWatch."""
    try:
        import boto3
    except ImportError:
        return {"success": False, "message": "boto3 library is not installed."}

    ak = access_key or settings.AWS_ACCESS_KEY_ID
    sk = secret_key or settings.AWS_SECRET_ACCESS_KEY
    reg = region or settings.AWS_REGION or "us-east-1"

    if not ak or not sk:
        return {"success": False, "message": "AWS Access Key ID and Secret Access Key are required."}

    try:
        sts = boto3.client("sts", aws_access_key_id=ak, aws_secret_access_key=sk, region_name=reg)
        identity = sts.get_caller_identity()
        return {
            "success": True,
            "account": identity.get("Account"),
            "arn": identity.get("Arn"),
            "userId": identity.get("UserId"),
            "region": reg,
            "message": f"Successfully authenticated as {identity.get('Arn')}"
        }
    except Exception as e:
        return {"success": False, "message": f"AWS connection failed: {str(e)}"}

def discover_aws_resources(cw_client) -> Dict[str, List[Dict[str, str]]]:
    """
    Scans CloudWatch metrics to discover active resources across AWS services in the user's account.
    Returns a dict mapping service keys to lists of resource dimensions.
    """
    discovered: Dict[str, List[Dict[str, str]]] = {
        "ec2": [],
        "rds": [],
        "alb": [],
        "api_gateway": [],
        "lambda": []
    }
    
    try:
        metrics_list = []
        try:
            # Query recently active metrics (past 3 hours)
            paginator = cw_client.get_paginator("list_metrics")
            for page in paginator.paginate(RecentlyActive="PT3H"):
                metrics_list.extend(page.get("Metrics", []))
                if len(metrics_list) >= 150:
                    break
        except Exception:
            # Fallback to standard list_metrics if RecentlyActive is not supported
            res = cw_client.list_metrics()
            metrics_list = res.get("Metrics", [])[:150]

        seen_dims = set()
        for m in metrics_list:
            ns = m.get("Namespace", "")
            for dim in m.get("Dimensions", []):
                name, val = dim.get("Name"), dim.get("Value")
                key = (ns, name, val)
                if key in seen_dims:
                    continue
                seen_dims.add(key)

                if ns == "AWS/EC2" and name == "InstanceId":
                    discovered["ec2"].append({"Name": name, "Value": val})
                elif ns == "AWS/RDS" and name == "DBInstanceIdentifier":
                    discovered["rds"].append({"Name": name, "Value": val})
                elif ns == "AWS/ApplicationELB" and name == "LoadBalancer":
                    discovered["alb"].append({"Name": name, "Value": val})
                elif ns == "AWS/ApiGateway" and name == "ApiName":
                    discovered["api_gateway"].append({"Name": name, "Value": val})
                elif ns == "AWS/Lambda" and name == "FunctionName":
                    discovered["lambda"].append({"Name": name, "Value": val})

    except Exception as e:
        logger.warning(f"[AWS Service] CloudWatch resource discovery failed (falling back to default queries): {e}")

    return discovered


def _get_metric_stat(
    cw_client,
    namespace: str,
    metric_name: str,
    start_time: datetime,
    end_time: datetime,
    dimensions: Optional[List[Dict[str, str]]] = None,
    stat: str = "Average",
    period: int = 300
) -> Optional[float]:
    """Helper to query a single CloudWatch metric safely."""
    try:
        kwargs = {
            "Namespace": namespace,
            "MetricName": metric_name,
            "StartTime": start_time,
            "EndTime": end_time,
            "Period": period,
            "Statistics": [stat]
        }
        if dimensions:
            kwargs["Dimensions"] = dimensions

        res = cw_client.get_metric_statistics(**kwargs)
        datapoints = sorted(res.get("Datapoints", []), key=lambda x: x.get("Timestamp", end_time))
        if datapoints:
            val = datapoints[-1].get(stat)
            return float(val) if val is not None else None
    except Exception as e:
        logger.debug(f"[AWS Service] Metric fetch failed for {namespace}/{metric_name}: {e}")
    return None


def fetch_cloudwatch_metrics() -> Optional[Dict[str, Any]]:
    """
    Discovers all active services in the user's AWS account and fetches real metrics
    from each discovered service (EC2, RDS, ALB, API Gateway, Lambda).
    Returns a combined evidence dictionary or None if AWS is unreachable.
    """
    cw_client = get_boto3_client("cloudwatch")
    if not cw_client:
        return None

    try:
        now = datetime.utcnow()
        start_time = now - timedelta(minutes=15)

        # 1. Discover active services in the account
        discovered = discover_aws_resources(cw_client)
        
        services_found_labels: List[str] = []
        service_metrics: Dict[str, Any] = {}
        has_any_datapoint = False

        # --- Service 1: EC2 Metrics ---
        ec2_instances = discovered.get("ec2", [])
        ec2_cpus = []
        if ec2_instances:
            for inst in ec2_instances[:5]:  # Check up to 5 instances
                inst_id = inst["Value"]
                services_found_labels.append(f"EC2 Instance ({inst_id})")
                val = _get_metric_stat(cw_client, "AWS/EC2", "CPUUtilization", start_time, now, [inst])
                if val is not None:
                    ec2_cpus.append(val)
                    has_any_datapoint = True
        else:
            # Fallback: query account-wide EC2 average if no instance dimension was discovered
            val = _get_metric_stat(cw_client, "AWS/EC2", "CPUUtilization", start_time, now)
            if val is not None:
                ec2_cpus.append(val)
                has_any_datapoint = True
                services_found_labels.append("EC2 (Account-wide)")

        avg_ec2_cpu = round(sum(ec2_cpus) / len(ec2_cpus), 2) if ec2_cpus else None
        service_metrics["ec2"] = {
            "available": bool(ec2_instances or ec2_cpus),
            "instances_monitored": len(ec2_instances) or (1 if ec2_cpus else 0),
            "cpu_utilization_pct": avg_ec2_cpu,
            "note": None if (ec2_instances or ec2_cpus) else "No EC2 instances detected in CloudWatch"
        }

        # --- Service 2: RDS Database Metrics ---
        rds_instances = discovered.get("rds", [])
        rds_connections = []
        rds_cpus = []
        if rds_instances:
            for rds in rds_instances[:5]:
                db_id = rds["Value"]
                services_found_labels.append(f"RDS Database ({db_id})")
                conn_val = _get_metric_stat(cw_client, "AWS/RDS", "DatabaseConnections", start_time, now, [rds])
                cpu_val = _get_metric_stat(cw_client, "AWS/RDS", "CPUUtilization", start_time, now, [rds])
                if conn_val is not None:
                    rds_connections.append(conn_val)
                    has_any_datapoint = True
                if cpu_val is not None:
                    rds_cpus.append(cpu_val)
                    has_any_datapoint = True
        else:
            # Fallback query for RDS without dimensions
            conn_val = _get_metric_stat(cw_client, "AWS/RDS", "DatabaseConnections", start_time, now)
            if conn_val is not None:
                rds_connections.append(conn_val)
                has_any_datapoint = True
                services_found_labels.append("RDS (Account-wide)")

        total_db_connections = int(sum(rds_connections)) if rds_connections else None
        avg_rds_cpu = round(sum(rds_cpus) / len(rds_cpus), 2) if rds_cpus else None
        service_metrics["rds"] = {
            "available": bool(rds_instances or rds_connections),
            "databases_monitored": len(rds_instances) or (1 if rds_connections else 0),
            "active_db_connections": total_db_connections,
            "cpu_utilization_pct": avg_rds_cpu,
            "note": None if (rds_instances or rds_connections) else "No RDS instances detected in CloudWatch"
        }

        # --- Service 3: Load Balancer (ALB) Metrics ---
        alb_instances = discovered.get("alb", [])
        alb_latencies = []
        alb_5xx_errors = []
        alb_requests = []
        if alb_instances:
            for alb in alb_instances[:3]:
                alb_name = alb["Value"]
                services_found_labels.append(f"ALB ({alb_name.split('/')[-2] if '/' in alb_name else alb_name})")
                rt = _get_metric_stat(cw_client, "AWS/ApplicationELB", "TargetResponseTime", start_time, now, [alb])
                errs = _get_metric_stat(cw_client, "AWS/ApplicationELB", "HTTPCode_Target_5XX_Count", start_time, now, [alb], stat="Sum")
                reqs = _get_metric_stat(cw_client, "AWS/ApplicationELB", "RequestCount", start_time, now, [alb], stat="Sum")
                if rt is not None:
                    alb_latencies.append(rt * 1000.0)  # Convert seconds to ms
                    has_any_datapoint = True
                if errs is not None:
                    alb_5xx_errors.append(errs)
                    has_any_datapoint = True
                if reqs is not None:
                    alb_requests.append(reqs)
        else:
            # Account-level ALB fallback
            rt = _get_metric_stat(cw_client, "AWS/ApplicationELB", "TargetResponseTime", start_time, now)
            if rt is not None:
                alb_latencies.append(rt * 1000.0)
                has_any_datapoint = True
                services_found_labels.append("ALB (Account-wide)")

        alb_latency_ms = round(sum(alb_latencies) / len(alb_latencies), 2) if alb_latencies else None
        total_5xx = sum(alb_5xx_errors) if alb_5xx_errors else 0.0
        total_reqs = sum(alb_requests) if alb_requests else 0.0
        alb_error_rate = round((total_5xx / total_reqs) * 100.0, 2) if total_reqs > 0 else None

        service_metrics["load_balancer"] = {
            "available": bool(alb_instances or alb_latencies),
            "target_response_time_ms": alb_latency_ms,
            "error_rate_5xx_pct": alb_error_rate,
            "request_count": int(total_reqs),
            "note": None if (alb_instances or alb_latencies) else "No ALB detected in CloudWatch"
        }

        # --- Service 4: API Gateway (if discovered) ---
        apigw_instances = discovered.get("api_gateway", [])
        apigw_latencies = []
        if apigw_instances:
            for api in apigw_instances[:3]:
                api_name = api["Value"]
                services_found_labels.append(f"API Gateway ({api_name})")
                lat = _get_metric_stat(cw_client, "AWS/ApiGateway", "Latency", start_time, now, [api])
                if lat is not None:
                    apigw_latencies.append(lat)
                    has_any_datapoint = True
            avg_apigw_lat = round(sum(apigw_latencies) / len(apigw_latencies), 2) if apigw_latencies else 0.0
            service_metrics["api_gateway"] = {"latency_ms": avg_apigw_lat}

        # --- Service 5: Lambda Functions (if discovered) ---
        lambda_funcs = discovered.get("lambda", [])
        lambda_durations = []
        lambda_errors = []
        if lambda_funcs:
            for fn in lambda_funcs[:5]:
                fn_name = fn["Value"]
                services_found_labels.append(f"Lambda ({fn_name})")
                dur = _get_metric_stat(cw_client, "AWS/Lambda", "Duration", start_time, now, [fn])
                err = _get_metric_stat(cw_client, "AWS/Lambda", "Errors", start_time, now, [fn], stat="Sum")
                if dur is not None:
                    lambda_durations.append(dur)
                    has_any_datapoint = True
                if err is not None:
                    lambda_errors.append(err)
                    has_any_datapoint = True
            service_metrics["lambda"] = {
                "functions_monitored": len(lambda_funcs),
                "avg_duration_ms": round(sum(lambda_durations) / len(lambda_durations), 2) if lambda_durations else 0.0,
                "total_errors": int(sum(lambda_errors)) if lambda_errors else 0
            }

        # Synthesize overall system metrics — use None for unavailable rather than 0
        primary_cpu = max(v for v in [avg_ec2_cpu, avg_rds_cpu] if v is not None) if any(v is not None for v in [avg_ec2_cpu, avg_rds_cpu]) else None
        primary_latency = alb_latency_ms
        if primary_latency is None and apigw_instances and "api_gateway" in service_metrics:
            primary_latency = service_metrics["api_gateway"]["latency_ms"]
        elif primary_latency is None and lambda_funcs and "lambda" in service_metrics:
            primary_latency = service_metrics["lambda"]["avg_duration_ms"]

        total_db_for_summary = total_db_connections if total_db_connections is not None else "N/A"
        evidence_summary = (
            f"AWS Services Discovered: {', '.join(services_found_labels) if services_found_labels else 'None active (check credentials/region)'}. "
            f"Metrics: EC2 CPU={f'{avg_ec2_cpu}%' if avg_ec2_cpu is not None else 'N/A'}, "
            f"RDS CPU={f'{avg_rds_cpu}%' if avg_rds_cpu is not None else 'N/A'}, "
            f"DB Connections={total_db_for_summary}, "
            f"Latency={f'{primary_latency}ms' if primary_latency is not None else 'N/A'}, "
            f"Error Rate={f'{alb_error_rate}%' if alb_error_rate is not None else 'N/A'}."
        )

        return {
            "timestamp": now.isoformat() + "Z",
            "services_discovered": services_found_labels,
            "cpu_utilization_pct": primary_cpu,
            "latency_ms": primary_latency,
            "error_rate_pct": alb_error_rate,
            "active_db_connections": total_db_connections,
            "service_metrics": service_metrics,
            "evidence_summary": evidence_summary,
            "has_live_datapoints": has_any_datapoint,
            "source": f"AWS CloudWatch ({settings.AWS_REGION})"
        }

    except Exception as e:
        logger.error(f"[AWS Service] CloudWatch multi-service metric fetch failed: {e}")
        return None

def fetch_cloudwatch_logs(log_group: str = "", filter_pattern: str = "ERROR") -> Optional[List[str]]:
    """
    Fetches recent error log lines from AWS CloudWatch Logs.
    Returns:
      - list of log strings if the query succeeded (may be empty if no matches — that's healthy, not an error)
      - None only if the query itself could not be made (no client, no log group, or an exception)
    """
    target_group = log_group or settings.CLOUDWATCH_LOG_GROUP
    logs_client = get_boto3_client("logs")

    if not logs_client or not target_group:
        return None

    try:
        start_time = int((datetime.utcnow() - timedelta(hours=1)).timestamp() * 1000)
        response = logs_client.filter_log_events(
            logGroupName=target_group,
            startTime=start_time,
            filterPattern=filter_pattern,
            limit=20
        )
        events = response.get("events", [])

        log_lines = []
        for ev in events:
            dt_str = datetime.utcfromtimestamp(ev.get("timestamp", 0) / 1000).strftime('%Y-%m-%d %H:%M:%S')
            log_lines.append(f"[{dt_str}] {ev.get('message', '').strip()}")

        logger.info(f"[AWS Service] Fetched {len(log_lines)} log events from CloudWatch group '{target_group}'.")
        return log_lines  # may legitimately be [] — that means "no matching errors", not "unreachable"

    except Exception as e:
        logger.error(f"[AWS Service] CloudWatch logs fetch failed for '{target_group}': {e}")
        return None