# OSRM AWS DEPLOYMENT: NEW YORK STATE
**Strategy:** EC2 Hibernation & Auto-Scaling for Cost Efficiency  
**Target Budget:** ~$6.00 / month (Usage Dependent)

This configuration deploys a high-performance OSRM instance on AWS designed to hibernate during periods of inactivity. This preserves the memory state for sub-60-second "warm" boots while minimizing compute costs. Security is handled via a Lambda-based gateway and custom headers.

---

## Phase 1: Instance Provisioning (EC2)

1. **Launch Instance:** Name it "osrm-server" using Ubuntu 22.04 LTS.
2. **Instance Type:** Select `t3.large` (8GB RAM is the minimum stable floor for NY).
3. **Key Pair:** Generate or select an existing `.pem` key.
4. **Storage & Encryption:** 
   - Set Root Volume to 40GB (gp3).
   - Under Advanced, **Enable Encryption** (Hibernation requires encrypted volumes).
5. **Advanced Details:** 
   - Set "Stop - Hibernate behavior" to **Enable**.
6. **Security Group (Firewall):**
   - SSH (22): Source: "My IP".
   - OSRM (5000): Source: "Anywhere" (or restricted to your Backend CIDR).

---

## Phase 2: OSRM Configuration & Data Processing

1. **Access the instance:** 
   ```bash
   ssh -i "your-key.pem" ubuntu@<public-ip>
   ```

2. **Setup Docker Environment:**
   ```bash
   sudo apt-get update && sudo apt-get install -y docker.io
   sudo usermod -aG docker ubuntu
   sudo reboot
   ```

3. **Process Map Data (Sequential execution):**
   ```bash
   wget https://download.geofabrik.de/north-america/us/new-york-latest.osm.pbf
   
   docker run -t -v "${PWD}:/data" ghcr.io/project-osrm/osrm-backend osrm-extract -p /opt/car.lua /data/new-york-latest.osm.pbf
   docker run -t -v "${PWD}:/data" ghcr.io/project-osrm/osrm-backend osrm-partition /data/new-york-latest.osrm
   docker run -t -v "${PWD}:/data" ghcr.io/project-osrm/osrm-backend osrm-customize /data/new-york-latest.osrm
   ```

4. **Initialize Service:**
   ```bash
   docker run -t -d -p 5000:5000 --name osrm-engine -v "${PWD}:/data" ghcr.io/project-osrm/osrm-backend osrm-routed --algorithm mld /data/new-york-latest.osrm
   docker update --restart always osrm-engine
   ```

5. **Configure Swap for Hibernation (Required):**
   ```bash
   sudo swapoff -a
   sudo fallocate -l 10G /swapfile
   sudo chmod 600 /swapfile
   sudo mkswap /swapfile
   sudo swapon /swapfile
   ```

---

## Phase 3: IAM Permissions

1. **Create a Lambda Execution Role** named `osrm-lambda-role`.
2. **Attach an Inline Policy** with the following JSON (Replace `ACCOUNT_ID` and `INSTANCE_ID`):
   ```json
   {
       "Version": "2012-10-17",
       "Statement": [
           {
               "Effect": "Allow",
               "Action": ["ec2:StartInstances", "ec2:StopInstances"],
               "Resource": "arn:aws:ec2:us-east-1:ACCOUNT_ID:instance/i-YOUR_ID"
           },
           {
               "Effect": "Allow",
               "Action": "ec2:DescribeInstances",
               "Resource": "*"
           }
       ]
   }
   ```

---

## Phase 4: Trigger Management (Wake & Sleep)

### Lambda 1: `osrm-wake` (Python 3.12)
- **Settings:** Set Timeout to 15s. Enable Function URL (Auth: NONE).
- **Role:** `osrm-lambda-role`
- **Logic:** Checks if instance is running. If stopped, triggers start. Returns IP.
- **Code:**
```python
import json
import boto3
import os

INSTANCE_ID = "i-YOUR_ID"
REGION = "us-east-1"
SECRET_VALUE = "YOUR_SECURE_SECRET_HERE"  # Or use os.environ.get('SECRET_VALUE')

def lambda_handler(event, context):
    headers = {k.lower(): v for k, v in event.get('headers', {}).items()}
    
    if headers.get('x-osrm-secret') != SECRET_VALUE:
        return {'statusCode': 401, 'body': json.dumps({"error": "Unauthorized"})}

    ec2 = boto3.client("ec2", region_name=REGION)
    res = ec2.describe_instances(InstanceIds=[INSTANCE_ID])
    instance = res["Reservations"][0]["Instances"][0]
    state = instance["State"]["Name"]

    if state == "running":
        ip = instance.get("PublicIpAddress")
        return {"statusCode": 200, "body": json.dumps({"status": "running", "ip": ip})}

    ec2.start_instances(InstanceIds=[INSTANCE_ID])
    return {"statusCode": 202, "body": json.dumps({"status": "starting"})}
```

### Lambda 2: `osrm-hibernate` (Python 3.12)
- **Role:** `osrm-lambda-role`
- **Logic:** Triggers `stop_instances` with `Hibernate=True`.
- **Code:**
```python
import boto3
import json

def lambda_handler(event, context):
    ec2 = boto3.client("ec2")
    ec2.stop_instances(InstanceIds=["i-YOUR_ID"], Hibernate=True)
    return {"statusCode": 200, "body": json.dumps({"status": "hibernating"})}
```

---

## Phase 5: Automation (CloudWatch)

1. **Create a CloudWatch Alarm** for the instance metric `NetworkIn`.
2. **Threshold:** 
   - **Period:** 30 Minutes.
   - **Condition:** `< 10000` Bytes.
3. **Action:** Set the "In Alarm" state to trigger the `osrm-hibernate` Lambda.

---

## Phase 6: Application Integration

1. **Environment Variables:**
   - `OSRM_WAKE_URL`: Your Lambda URL.
   - `OSRM_WAKE_SECRET`: Your defined security token.

2. **Boot Sequence Logic (Backend Implementation):**
   - **Step A:** Ping the Wake Lambda with the secret header.
   - **Step B:** If status is "starting," poll every 5s until "running" is returned with an IP.
   - **Step C:** Once the instance is up, softly poll the OSRM port (5000). 
     > *Note:* Because hibernation seamlessly preserves Docker's RAM state, the routing engine will typically answer near-instantaneously organically, but keeping a safety-net polling loop guarantees flawless integration.

---

## Cost Analysis (Estimated)

- **EBS Storage (Persistent):** ~$3.20/mo (40GB @ $0.08/GB).
- **Compute (Active):** ~$0.083/hr.
  - 10 hours/week usage = ~$3.32/mo.
- **Serverless/Monitoring:** Covered under AWS Free Tier.

**TOTAL MONTHLY BILL: ~$6.50**
