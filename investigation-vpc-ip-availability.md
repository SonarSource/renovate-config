# Investigation: [GH Runner Infra] VPC IP Address Availability - Prod

| Field | Value |
|---|---|
| **Date** | 2026-04-08 |
| **Monitor ID** | 102480265 |
| **Status** | ALERT (P2) |
| **Service** | Github Action Runners Infra |
| **Owner** | development-infra-squad |
| **Runbook** | https://xtranet-sonarsource.atlassian.net/wiki/spaces/Platform/pages/4992335882 |

## Summary

Both private subnets in the `github-runners-prod` VPC (`083f865784cbb6379`) in `eu-central-1` have **exhausted all available IP addresses**, hitting 0 IPs. This is preventing new EKS pods and nodes from launching for GitHub Actions self-hosted runners.

## Monitor Configuration

- **Query:** `min(last_1h):min:aws.vpc.subnet.available_ip_address_count{vpc:083f865784cbb6379,name:github-runners-prod-private-subnet-*} by {availability-zone,subnet} < 200`
- **Critical threshold:** < 200 available IPs
- **AWS Account:** 275878209202 (re-team-prod)
- **Notification:** `@slack-squad-eng-xp-notifs`

## Affected Subnets

| Subnet ID | AZ | Current IPs | Status |
|---|---|---|---|
| `014f6af585ca748e1` | `eu-central-1a` | **0** | CRITICAL - Exhausted |
| `0a6824aa2076f7f94` | `eu-central-1b` | **0** | CRITICAL - Exhausted |

## Alert Timeline (2026-04-08)

1. **~10:57 UTC** — Warning triggered for `eu-central-1b` (391 IPs available)
2. **~14:06 UTC** — Warning triggered for `eu-central-1a` (476 IPs available)
3. **~14:42 UTC** — Critical alert triggered for `eu-central-1b` (151 IPs available)
4. **~15:30 UTC** — Critical alert triggered for `eu-central-1a` (6 IPs available)
5. **~15:30+ UTC** — Both subnets hit **0 available IPs**

## Detailed IP Exhaustion Timeline (Last 4 Hours)

### eu-central-1a (subnet `014f6af585ca748e1`)
- 11:35–13:00 UTC: Steady at ~596 IPs
- ~13:15 UTC: Dropped to ~476 IPs
- ~13:45 UTC: Dropped to ~536 IPs (brief recovery)
- ~14:15 UTC: Dropped to ~276 IPs
- ~14:30 UTC: Brief recovery to ~396 IPs
- ~15:00 UTC: Sharp drop to **6 IPs**
- ~15:30 UTC: **0 IPs** — fully exhausted

### eu-central-1b (subnet `0a6824aa2076f7f94`)
- 11:35–13:00 UTC: Steady at ~391 IPs
- ~14:15 UTC: Dropped to ~151 IPs
- ~14:30 UTC: Brief recovery to ~391 IPs
- ~15:00 UTC: Sharp drop to **0 IPs**
- ~15:30 UTC: **0 IPs** — fully exhausted

## 7-Day Pattern Analysis

The 7-day trend reveals a **recurring daily cycle**:
- **Nighttime (EU):** IPs recover to 3,000–3,800+ range as runner workloads scale down
- **Business hours (EU):** IPs drop as CI/CD workloads spin up pods/nodes

However, the situation has been **progressively worsening**:

| Date | Lowest IP Count (approx) | Severity |
|---|---|---|
| Apr 1 (Tue) | ~1,100 | Normal |
| Apr 2 (Wed) | ~470 | Low (first dip below 500) |
| Apr 3 (Thu) | ~1,640 | Normal |
| Apr 4 (Fri) | ~2,860 | Normal (weekend approaching) |
| Apr 5 (Sat) | ~1,700 | Normal (weekend) |
| Apr 6 (Sun) | ~1,650 | Normal (weekend) |
| Apr 7 (Mon) | ~576 | Warning zone |
| **Apr 8 (Tue)** | **0** | **CRITICAL — Exhausted** |

The data shows a clear escalation from last Wednesday (Apr 2) through today, with each business day pushing the IP count lower than the previous one.

## Root Cause Analysis

The IP exhaustion is driven by increasing demand for EKS pods/nodes in the GitHub runners infrastructure. Contributing factors likely include:

1. **Growing CI/CD workload:** More GitHub Actions jobs requiring self-hosted runners
2. **Pod/node scaling:** EKS autoscaler provisioning more nodes and pods, each consuming IPs from the VPC subnets
3. **Subnet CIDR sizing:** The current subnet allocation may be insufficient for peak workload
4. **Possible IP leak:** Pods or nodes not releasing IPs promptly after job completion (needs further investigation)

## Impact

- **New EKS pods cannot be scheduled** — any GitHub Actions job requiring a self-hosted runner will fail or queue indefinitely
- **Node autoscaling blocked** — new EC2 worker nodes cannot join the EKS cluster
- **CI/CD pipeline disruption** — all teams relying on self-hosted runners in production are affected

## Recommended Actions

### Immediate (Mitigation)
1. **Follow the runbook** at the link above for standard remediation steps
2. **Scale down idle runners** to free up IPs
3. **Check for stuck/orphaned pods** that may be holding IPs unnecessarily
4. **Monitor for natural recovery** — historically IPs recover in the evening EU time as workloads decrease

### Short-Term
1. **Expand CIDR range** for the private subnets if possible
2. **Add additional subnets** in available AZs to increase the IP pool
3. **Review EKS pod density** — consider using prefix delegation to assign more IPs per ENI

### Long-Term
1. **Right-size the VPC/subnet allocation** based on peak workload patterns
2. **Implement pod-level IP management** with CNI prefix delegation or secondary CIDR blocks
3. **Add capacity planning alerts** at higher thresholds (e.g., warn at 1000, critical at 500) to provide earlier warning
4. **Consider the weekly trend** — Tuesday/Wednesday appear to be peak CI/CD days; plan capacity accordingly
