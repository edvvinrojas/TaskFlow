import boto3
import argparse
import time

DEFAULT_REGION = "us-east-1"
DEFAULT_AMI = "ami-0c02fb55956c7d316"
INSTANCE_TYPE = "t3.micro"
APP_PORT = 8000
APP_NAME = "taskflow"

parser = argparse.ArgumentParser(description="Despliega TaskFlow en AWS")
parser.add_argument("--region", default=DEFAULT_REGION)
parser.add_argument("--key-name", required=True, help="Nombre del Key Pair en AWS")
parser.add_argument("--access-key", default=None)
parser.add_argument("--secret-key", default=None)
parser.add_argument("--repo-url", required=True, help="URL de tu repositorio Git")
parser.add_argument("--app-branch", default="main")
args = parser.parse_args()

session_kwargs = {"region_name": args.region}
if args.access_key and args.secret_key:
    session_kwargs["aws_access_key_id"] = args.access_key
    session_kwargs["aws_secret_access_key"] = args.secret_key

session = boto3.Session(**session_kwargs)
ec2 = session.client("ec2")
ec2_res = session.resource("ec2")
s3 = session.client("s3")


def create_s3_bucket():
    bucket_name = f"{APP_NAME}-attachments-{int(time.time())}"
    try:
        if args.region == "us-east-1":
            s3.create_bucket(Bucket=bucket_name)
        else:
            s3.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={"LocationConstraint": args.region},
            )
        s3.put_public_access_block(
            Bucket=bucket_name,
            PublicAccessBlockConfiguration={
                "BlockPublicAcls": True,
                "IgnorePublicAcls": True,
                "BlockPublicPolicy": True,
                "RestrictPublicBuckets": True,
            },
        )
    except Exception:
        pass
    return bucket_name


def create_security_group():
    sg_name = f"{APP_NAME}-sg"
    try:
        sg = ec2.create_security_group(
            GroupName=sg_name, Description=f"SG para {APP_NAME}"
        )
        sg_id = sg["GroupId"]
        ec2.authorize_security_group_ingress(
            GroupId=sg_id,
            IpPermissions=[
                {
                    "IpProtocol": "tcp",
                    "FromPort": 22,
                    "ToPort": 22,
                    "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
                },
                {
                    "IpProtocol": "tcp",
                    "FromPort": 80,
                    "ToPort": 80,
                    "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
                },
                {
                    "IpProtocol": "tcp",
                    "FromPort": APP_PORT,
                    "ToPort": APP_PORT,
                    "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
                },
            ],
        )
        return sg_id
    except Exception:
        sgs = ec2.describe_security_groups(
            Filters=[{"Name": "group-name", "Values": [sg_name]}]
        )
        return sgs["SecurityGroups"][0]["GroupId"]


def build_user_data(bucket_name):
    return f"""#!/bin/bash
set -e
exec > /var/log/taskflow-setup.log 2>&1

dnf update -y
dnf install -y python3 python3-pip git

cd /home/ec2-user
git clone {args.repo_url} app
cd app
git checkout {args.app_branch}

pip3 install -r requirements.txt

cat > /etc/systemd/system/taskflow.service <<'UNIT'
[Unit]
Description=TaskFlow FastAPI
After=network.target

[Service]
User=ec2-user
WorkingDirectory=/home/ec2-user/app
EnvironmentFile=/home/ec2-user/app/.env
ExecStart=/usr/bin/python3 -m uvicorn app.main:app --host 0.0.0.0 --port {APP_PORT}
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable taskflow
systemctl start taskflow
"""


def launch_ec2(sg_id, user_data):
    instances = ec2_res.create_instances(
        ImageId=DEFAULT_AMI,
        InstanceType=INSTANCE_TYPE,
        KeyName=args.key_name,
        MinCount=1,
        MaxCount=1,
        SecurityGroupIds=[sg_id],
        UserData=user_data,
        TagSpecifications=[
            {
                "ResourceType": "instance",
                "Tags": [{"Key": "Name", "Value": APP_NAME}],
            }
        ],
    )
    instance = instances[0]
    instance.wait_until_running()
    instance.reload()
    return instance


def main():
    bucket_name = create_s3_bucket()
    sg_id = create_security_group()
    user_data = build_user_data(bucket_name)
    instance = launch_ec2(sg_id, user_data)

    ip = instance.public_ip_address

    print(f"Instancia : {instance.id}")
    print(f"IP publica: {ip}")
    print(f"Bucket S3 : {bucket_name}")
    print(f"App URL   : http://{ip}:{APP_PORT}")
    print(f"Swagger   : http://{ip}:{APP_PORT}/docs")
    print(f"Logs SSH  : ssh -i {args.key_name}.pem ec2-user@{ip}")
    print(f"Setup log : tail -f /var/log/taskflow-setup.log")

    with open("deploy_output.txt", "w") as f:
        f.write(f"instance_id={instance.id}\n")
        f.write(f"public_ip={ip}\n")
        f.write(f"s3_bucket={bucket_name}\n")
        f.write(f"app_url=http://{ip}:{APP_PORT}\n")


if __name__ == "__main__":
    main()
