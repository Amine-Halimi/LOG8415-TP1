import boto3
import sys, os, time
import subprocess
from botocore.exceptions import ClientError
import paramiko

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
        return instances
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
        lb_dns_name = response['LoadBalancers'][0]['DNSName']
        print(f"Created Load Balancer DNS: {lb_dns_name}")
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
        print(f"Created Target Group: {name}")
        return target_group_arn
    except Exception as e:
        print(f"Error creating target group: {e}")
        sys.exit(1)

        
def register_targets(elbv2_client, target_group_arn, instance_ids):
    try:
        targets = [{'Id': instance_id} for instance_id in instance_ids]
        elbv2_client.register_targets(
            TargetGroupArn=target_group_arn,
            Targets=targets
        )
        print(f"Registered instances: {instance_ids}")
        return
    except Exception as e:
        print(f"Error registering targets: {e}")
        # Wait if the instances are not running and do it again
        time.sleep(5)
        return register_targets(elbv2_client, target_group_arn, instance_ids)

def transfer_file(instance_ip, key_file, local_file, remote_file):
    try:
        # Create a SSH client instance
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # Connect to the instance
        ssh_client.connect(instance_ip, username='ubuntu', key_filename=key_file)

        # Crear a SCP instance
        scp = paramiko.SFTPClient.from_transport(ssh_client.get_transport())
        
        # Transfer the file
        scp.put(local_file, remote_file)
        
        # Close connections
        scp.close()
        ssh_client.close()
        print(f"File {local_file} transferred to {instance_ip}:{remote_file}")
    
    except Exception as e:
        print(f"Error transferring file to {instance_ip}: {e}")

def create_listener(elbv2_client, load_balancer_arn, tg_cluster1_arn, tg_cluster2_arn):
    try:
        response = elbv2_client.create_listener(
            LoadBalancerArn=load_balancer_arn,
            Protocol='HTTP',
            Port=8000,
            DefaultActions=[
                {
                    'Type': 'fixed-response',
                    'FixedResponseConfig': {
                        'ContentType': 'text/plain',
                        'MessageBody': '404 Not Found',
                        'StatusCode': '404'
                    }
                }
            ]
        )
        listener_arn = response['Listeners'][0]['ListenerArn']
        print("Listener created for load balancer without rules.")

        # Now create rules for path-based routing
        create_listener_rules(elbv2_client, listener_arn, tg_cluster1_arn, tg_cluster2_arn)
    except ClientError as e:
        print(f"Error creating listener: {e}")

def create_listener_rules(elbv2_client, listener_arn, tg_cluster1_arn, tg_cluster2_arn):
    try:
        # Rule for /cluster1
        elbv2_client.create_rule(
            ListenerArn=listener_arn,
            Conditions=[
                {
                    'Field': 'path-pattern',
                    'Values': ['/cluster1*']
                }
            ],
            Priority=1,
            Actions=[
                {
                    'Type': 'forward',
                    'TargetGroupArn': tg_cluster1_arn
                }
            ]
        )
        print("Rule created for /cluster1.")

        # Rule for /cluster2
        elbv2_client.create_rule(
            ListenerArn=listener_arn,
            Conditions=[
                {
                    'Field': 'path-pattern',
                    'Values': ['/cluster2*']
                }
            ],
            Priority=2,
            Actions=[
                {
                    'Type': 'forward',
                    'TargetGroupArn': tg_cluster2_arn
                }
            ]
        )
        print("Rule created for /cluster2.")
    except ClientError as e:
        print(f"Error creating listener rules: {e}")


def load_fastest_instances():
    try:
        with open("fastest_instances.txt", "r") as f:
            lines = f.readlines()

        fastest_micro = {}
        fastest_large = {}

        for line in lines:
            if "t2.micro" in line:
                fastest_micro = extract_instance_info(line)
            elif "t2.large" in line:
                fastest_large = extract_instance_info(line)

        return fastest_micro, fastest_large
    except Exception as e:
        print(f"Error reading fastest instances file: {e}")
        return None, None


def extract_instance_info(line):
    parts = line.split()
    instance_id = parts[3]
    public_ip = parts[-1]
    return {
        'InstanceId': instance_id,
        'PublicIpAddress': public_ip
    }

def get_registered_targets(elbv2_client, target_group_arn):
    try:
        response = elbv2_client.describe_target_health(TargetGroupArn=target_group_arn)
        registered_targets = [target['Target']['Id'] for target in response['TargetHealthDescriptions']]
        return registered_targets
    except Exception as e:
        print(f"Error fetching registered targets: {e}")
        return []

def update_target_groups(elbv2_client, fastest_micro, fastest_large, tg_cluster1_arn, tg_cluster2_arn):
    try:
        # Get the registered instances in each target group
        registered_micro_targets = get_registered_targets(elbv2_client, tg_cluster1_arn)
        registered_large_targets = get_registered_targets(elbv2_client, tg_cluster2_arn)

        # Deregister all instances in cluster1 except the fastest one
        for instance_id in registered_micro_targets:
            #print(f"IDS: {instance_id} != {fastest_micro['InstanceId']}")
            if instance_id != fastest_micro['InstanceId']:
                response = elbv2_client.deregister_targets(
                    TargetGroupArn=tg_cluster1_arn,
                    Targets=[{'Id': instance_id}]
                )
                print(f"Deregistered instance {instance_id} from cluster1")

        #time.sleep(10)
        #print(f"size: {len(get_registered_targets(elbv2_client, tg_cluster1_arn))}")
        # Register the fastest instance for cluster1 if not already registered
        if fastest_micro['InstanceId'] not in registered_micro_targets:
            response = elbv2_client.register_targets(
                TargetGroupArn=tg_cluster1_arn,
                Targets=[{'Id': fastest_micro['InstanceId']}]
            )
            print(f"Registered fastest t2.micro, size: {len(get_registered_targets(elbv2_client, tg_cluster1_arn))}")

        # Deregister all instances in cluster2 except the fastest one
        for instance_id in registered_large_targets:
            #print(f"IDS: {instance_id} != {fastest_large['InstanceId']}")
            if instance_id != fastest_large['InstanceId']:
                response = elbv2_client.deregister_targets(
                    TargetGroupArn=tg_cluster2_arn,
                    Targets=[{'Id': instance_id}]
                )
                print(f"Deregistered instance {instance_id} from cluster2")

        #time.sleep(10)
        #print(f"size: {len(get_registered_targets(elbv2_client, tg_cluster2_arn))}")

        # Register the fastest instance for cluster2 if not already registered
        if fastest_large['InstanceId'] not in registered_large_targets:
            response = elbv2_client.register_targets(
                TargetGroupArn=tg_cluster2_arn,
                Targets=[{'Id': fastest_large['InstanceId']}]
            )
            print(f"Registered fastest t2.large, size: {len(get_registered_targets(elbv2_client, tg_cluster2_arn))}")

    except Exception as e:
        print(f"Error updating target groups: {e}")

def main():
    # Initialize AWS clients
    ec2_client = boto3.client('ec2')
    ec2_resource = boto3.resource('ec2')
    elbv2_client = boto3.client('elbv2')

    # Parameters
    IMAGE_ID = 'ami-0e86e20dae9224db8'
    INSTANCE_micro, INSTANCE_large = 2, 2

    # Get VPC, Key name (has to be brand new everytime, is deleted in terminate.py), security group and subnet
    vpc_id = get_vpc_id(ec2_client)
    key_name = get_key_pair(ec2_client)
    security_group_id = get_security_group(ec2_client, vpc_id)
    subnet_ids = get_subnet(ec2_client, vpc_id)

    # Launch Instances micro and large
    instances_cluster1 = []
    instances_cluster2 = []
    
    if INSTANCE_micro > 0:
        instances_cluster1 = launch_instances(ec2_resource, IMAGE_ID, INSTANCE_micro, 't2.micro', key_name, security_group_id, subnet_ids[0])
    
    if INSTANCE_large > 0:
        instances_cluster2 = launch_instances(ec2_resource, IMAGE_ID, INSTANCE_large, 't2.large', key_name, security_group_id, subnet_ids[1])

    # Wait until the instances are "running" and obtain their public IPs
    instance_ips = []
    for instance in instances_cluster1 + instances_cluster2:
        instance.wait_until_running()
        instance.reload() 
        instance_ips.append(instance.public_ip_address)

    # Print the public IPs
    print("Public IPs of instances:", instance_ips)

    time.sleep(60)

    # Transfer my_fastapi.py to all instances
    key_file_path = os.path.join(os.path.expanduser('~/.aws'), f"{key_name}.pem")
    local_file_path = "my_fastapi.py"

    for ip in instance_ips:
        transfer_file(ip, key_file_path, local_file_path, "/home/ubuntu/my_fastapi.py")

    # Create load balancer
    lb_arn = create_load_balancer(elbv2_client, security_group_id, subnet_ids)

    # Create target groups
    tg_cluster1_arn = create_target_group(elbv2_client, 'cluster1', vpc_id)
    tg_cluster2_arn = create_target_group(elbv2_client, 'cluster2', vpc_id)

    # Register instances to target groups
    instance_ids_cluster1 = [instance.id for instance in instances_cluster1]
    instance_ids_cluster2 = [instance.id for instance in instances_cluster2]
    register_targets(elbv2_client, tg_cluster1_arn, instance_ids_cluster1)
    register_targets(elbv2_client, tg_cluster2_arn, instance_ids_cluster2)

    # Create listener for load balancer
    create_listener(elbv2_client, lb_arn, tg_cluster1_arn, tg_cluster2_arn)
    time.sleep(180)

    while True:
        # Load the fastest instances
        fastest_micro, fastest_large = load_fastest_instances()

        if fastest_micro and fastest_large:
            # Update target groups with the fastest instances
            update_target_groups(elbv2_client, fastest_micro, fastest_large, tg_cluster1_arn, tg_cluster2_arn)
        else:
            time.sleep(10)

        time.sleep(1)


if __name__ == "__main__":
    main()

    #test again

