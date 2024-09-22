import boto3
import sys, os
import subprocess
from botocore.exceptions import ClientError

def get_key_pair(ec2_client):
    try:
        key_name = "tp1" 
        response = ec2_client.create_key_pair(KeyName=key_name)

        # Extract private key
        private_key = response['KeyMaterial']

        # Path to save the key
        save_directory = os.path.expanduser('~/.aws')
        key_file_path = os.path.join(save_directory, f"{key_name}.pem")

        # Save the key to directory
        with open(key_file_path, 'w') as file:
            file.write(private_key)

        os.chmod(key_file_path, 0o400)
        print(f"Using Key Pair: {key_name}")
        return key_name

    except ClientError as e:
        print(f"Error retrieving key pairs: {e}")
        sys.exit(1)

def get_security_group(ec2_client, vpc_id):
    try:
        response = ec2_client.describe_security_groups(
            Filters=[
                {
                    'Name': 'group-name',
                    'Values': ['default']
                },
                {
                    'Name': 'vpc-id',
                    'Values': [vpc_id]
                }
            ]
        )
        security_groups = response.get('SecurityGroups', [])
        if not security_groups:
            print("Error: Default security group not found.")
            sys.exit(1)

        print(f"Using Security Group ID: {security_groups[0]['GroupId']}")
        return security_groups[0]['GroupId']
    except ClientError as e:
        print(f"Error retrieving security groups: {e}")
        sys.exit(1)

def get_subnet(ec2_client, vpc_id):
    try:
        response = ec2_client.describe_subnets(
            Filters=[
                {
                    'Name': 'vpc-id',
                    'Values': [vpc_id]
                }
            ]
        )
        subnets = response.get('Subnets', [])
        if not subnets:
            print("Error: No subnets found in the VPC.")
            sys.exit(1)

        print(f"Using Subnet ID: {subnets[0]['SubnetId']} and {subnets[1]['SubnetId']}")
        return [subnets[0]['SubnetId'], subnets[1]['SubnetId']]
    except ClientError as e:
        print(f"Error retrieving subnets: {e}")
        sys.exit(1)

def get_vpc_id(ec2_client):
    try:
        response = ec2_client.describe_vpcs()
        vpcs = response.get('Vpcs', [])
        if not vpcs:
            print("Error: No VPCs found.")
            sys.exit(1)
        print(f"Using VPC ID: {vpcs[0]['VpcId']}")
        return vpcs[0]['VpcId']
    except ClientError as e:
        print(f"Error retrieving VPCs: {e}")
        sys.exit(1)

def launch_instances(ec2_resource, image_id, count, instance_type, key_name, security_group_id, subnet_id):

    # Comands for the instance, so you dont have to connect (ssh) to the instance. It waits until you copy the fastAPI file and then activates it
    # You have to wait circa 30sec until you can test connection through web browser in this format: publicIP:8000
    user_data_script = '''#!/bin/bash
        sudo apt update -y
        sudo apt install -y python3-pip python3-venv
        cd /home/ubuntu
        python3 -m venv venv
        echo "source venv/bin/activate" >> /home/ubuntu/.bashrc
        source venv/bin/activate
        pip install fastapi uvicorn

        # Wait for the my_fastapi.py file to be transferred
        while [ ! -f /home/ubuntu/my_fastapi.py ]; do
            sleep 5
        done

        # Start the FastAPI application
        nohup uvicorn my_fastapi:app --host 0.0.0.0 --port 8000 &
    '''
    try:
        instances = ec2_resource.create_instances(
            ImageId=image_id,
            MinCount=1,
            MaxCount=count,
            InstanceType=instance_type,
            KeyName=key_name,
            SecurityGroupIds=[security_group_id],
            SubnetId=subnet_id,
            UserData=user_data_script,
            TagSpecifications=[
                {
                    'ResourceType': 'instance',
                    'Tags': [
                        {
                            'Key': 'Name',
                            'Value': 'LabInstance'
                        }
                    ]
                }
            ]
        )
        print(f"Launched {len(instances)} instance(s) successfully.")
    except ClientError as e:
        print(f"Error launching instances: {e}")
        sys.exit(1)

def create_load_balancer(elbv2_client, security_group_id, subnet_ids):
    try:
        response = elbv2_client.create_load_balancer(
            Name='MyLoadBalancer',
            Subnets=subnet_ids,
            SecurityGroups=[security_group_id],
            Scheme='internet-facing',
            Type='application',
            IpAddressType='ipv4'
        )
        lb_arn = response['LoadBalancers'][0]['LoadBalancerArn']
        print(f"Created Load Balancer: {lb_arn}")
        return lb_arn
    except Exception as e:
        print(f"Error creating load balancer: {e}")
        sys.exit(1)

def create_target_group(elbv2_client, name, vpc_id):
    try:
        response = elbv2_client.create_target_group(
            Name=name,
            Protocol='HTTP',
            Port=8000,
            VpcId=vpc_id,
            HealthCheckProtocol='HTTP',
            HealthCheckPort='8000',
            HealthCheckPath='/',
            TargetType='instance'
        )
        target_group_arn = response['TargetGroups'][0]['TargetGroupArn']
        print(f"Created Target Group: {name}, ARN: {target_group_arn}")
        return target_group_arn
    except Exception as e:
        print(f"Error creating target group: {e}")
        sys.exit(1)

def main():
    # Initialize AWS clients
    ec2_client = boto3.client('ec2')
    ec2_resource = boto3.resource('ec2')
    elbv2_client = boto3.client('elbv2')

    # Parameters
    IMAGE_ID = 'ami-0e86e20dae9224db8'   # Replace with your AMI ID
    INSTANCE_micro, INSTANCE_large = 1, 1

    # Get VPC, Key name (has to be brand new everytime, is deleted in terminate.py), security group and subnet
    vpc_id = get_vpc_id(ec2_client)
    key_name = get_key_pair(ec2_client)
    security_group_id = get_security_group(ec2_client, vpc_id) # Here you have to have already created one security group with Inbound rules: [SSH-TCP-SecurityGroupId, SSH-TCP-0.0.0.0, CustomTCP-TCP-MyLocalIP]
    subnet_ids = get_subnet(ec2_client, vpc_id) # Here you have to have at least two subnets created

    # Launch Instances micro and large
    if INSTANCE_micro > 0:
        launch_instances( ec2_resource, IMAGE_ID, INSTANCE_micro, 't2.micro', key_name, security_group_id, subnet_ids[0] )
    if INSTANCE_large > 0:
        launch_instances( ec2_resource, IMAGE_ID, INSTANCE_large, 't2.large', key_name, security_group_id, subnet_ids[1] )

    # Create load balancer
    lb_arn = create_load_balancer(elbv2_client, security_group_id, subnet_ids)

    # Create cluster targets
    tg_cluster1_arn = create_target_group(elbv2_client, 'cluster1', vpc_id)
    tg_cluster2_arn = create_target_group(elbv2_client, 'cluster2', vpc_id)


if __name__ == "__main__":
    main()

