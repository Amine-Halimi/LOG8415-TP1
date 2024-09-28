import boto3
import sys, os, time
import datetime
from botocore.exceptions import ClientError
import paramiko

def get_key_pair(ec2_client):
    key_name = "tp1"
    try:
        # You don't use the 'response' variable here, so this line can be removed
        ec2_client.describe_key_pairs(KeyNames=[key_name])
        print(f"Key Pair {key_name} already exists. Using the existing key.")
        return key_name

    except ClientError as e:
        if 'InvalidKeyPair.NotFound' in str(e):
            try:
                # You can keep this response if you want to handle its data
                response = ec2_client.create_key_pair(KeyName=key_name)

                # If you're not using 'response' elsewhere, this line can be simplified or removed
                private_key = response['KeyMaterial']

                # Save the key to directory
                save_directory = os.path.expanduser('~/.aws')
                key_file_path = os.path.join(save_directory, f"{key_name}.pem")

                with open(key_file_path, 'w') as file:
                    file.write(private_key)

                os.chmod(key_file_path, 0o400)
                print(f"Created and using Key Pair: {key_name}")
                return key_name
            except ClientError as e:
                print(f"Error creating key pair: {e}")
                sys.exit(1)
        else:
            print(f"Error retrieving key pairs: {e}")
            sys.exit(1)

def get_security_group(ec2_client, vpc_id):
    try:
        print(f"Fetching security group for VPC ID: {vpc_id}")
        response = ec2_client.describe_security_groups(
            Filters=[
                {
                    'Name': 'group-name',
                    'Values': ['default']  # Ensure this is the correct group name
                },
                {
                    'Name': 'vpc-id',
                    'Values': [vpc_id]  # Ensure this VPC ID is correct
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

def launch_ec2_instances(ec2_client, image_id, instance_type, key_name, security_group_id, subnet_id, num_instances):
    """
    Launches EC2 instances.
    Args:
        ec2_client: The EC2 client.
        image_id: The AMI ID for the instance.
        instance_type: The type of instance (e.g., 't2.micro').
        key_name: The key pair name to use for SSH access.
        security_group_id: The security group ID.
        subnet_id: The subnet ID.
        num_instances: Number of instances to launch.
    Returns:
        List of EC2 instance objects.
    """
    try:
        # Launch instances
        response = ec2_client.run_instances(
            ImageId=image_id,
            InstanceType=instance_type,
            KeyName=key_name,
            SecurityGroupIds=[security_group_id],
            SubnetId=subnet_id,
            MinCount=num_instances,  # Minimum number of instances to launch
            MaxCount=num_instances,  # Maximum number of instances to launch
            TagSpecifications=[{
                'ResourceType': 'instance',
                'Tags': [{'Key': 'Name', 'Value': 'Cluster Instance'}]
            }]
        )

        # Use the EC2 resource to interact with the instances
        ec2_resource = boto3.resource('ec2')

        # Retrieve instance objects using the InstanceId
        instance_objects = [ec2_resource.Instance(instance['InstanceId']) for instance in response['Instances']]

        print(f"Launched {num_instances} {instance_type} instances.")
        return instance_objects

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
        # Create an SSH client instance
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

        # Rule for /cluster1 using the fastest t2.micro instance
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
        print(f"Rule created for /cluster1 with fastest t2.micro instance: {tg_cluster1_arn}.")

        # Rule for /cluster2 using the fastest t2.large instance
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
        print(f"Rule created for /cluster2 with fastest t2.large instance: {tg_cluster2_arn}.")

    except ClientError as e:
        print(f"Error creating listener rules: {e}")

def get_instance_metrics(instance_id):
    """
    Query CloudWatch for the CPU utilization of a given instance.
    Args:
        instance_id: The ID of the EC2 instance.
    Returns:
        The average CPU utilization of the instance over the last 5 minutes.
    """
    cloudwatch = boto3.client('cloudwatch')

    # Fetch CPU Utilization data for the last 5 minutes
    response = cloudwatch.get_metric_statistics(
        Namespace='AWS/EC2',
        MetricName='CPUUtilization',
        Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}],
        StartTime=datetime.datetime.utcnow() - datetime.timedelta(minutes=5),
        EndTime=datetime.datetime.utcnow(),
        Period=300,  # 5-minute period
        Statistics=['Average']
    )

    # Extract the CPU utilization value from the response
    datapoints = response.get('Datapoints', [])
    if not datapoints:
        return None

    # Return the average CPU utilization
    return datapoints[0]['Average']

def get_target_group_arn(elbv2_client, instance_id):
    """
    Retrieve the Target Group ARN for a given instance.
    Args:
        elbv2_client: The boto3 Elastic Load Balancing v2 client.
        instance_id: The ID of the EC2 instance.
    Returns:
        The target group ARN associated with the instance.
    """
    response = elbv2_client.describe_target_health(
        TargetGroupArn='your-target-group-arn',  # Replace with your logic to find the target group
        Targets=[
            {
                'Id': instance_id
            }
        ]
    )

    target_group_arn = None
    for tg in response['TargetHealthDescriptions']:
        if tg['Target']['Id'] == instance_id:
            target_group_arn = tg['TargetGroupArn']
            break

    return target_group_arn

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

def update_target_group(elbv2_client, fastest_instance, target_group_arn, registered_targets, instance_type):
    """
    Update the target group by deregistering all instances except the fastest one
    and registering the fastest instance if it's not already registered.
    """
    try:
        # Deregister all instances except the fastest one
        if fastest_instance['InstanceId'] not in registered_targets:
            print(f"Deregistering all {instance_type} instances except {fastest_instance['InstanceId']}")
            for instance_id in registered_targets:
                if instance_id != fastest_instance['InstanceId']:
                    elbv2_client.deregister_targets(
                        TargetGroupArn=target_group_arn,
                        Targets=[{'Id': instance_id}]
                    )
                    print(f"Deregistered instance {instance_id} from {instance_type} target group")
            # Register the fastest instance
            elbv2_client.register_targets(
                TargetGroupArn=target_group_arn,
                Targets=[{'Id': fastest_instance['InstanceId']}]
            )
            print(f"Registered fastest {instance_type} instance {fastest_instance['InstanceId']} to target group")
        else:
            print(f"Fastest {instance_type} instance {fastest_instance['InstanceId']} already registered")
    except Exception as e:
        print(f"Error updating {instance_type} target group: {e}")


def update_target_groups(elbv2_client, fastest_micro, fastest_large, tg_cluster1_arn, tg_cluster2_arn):
    try:
        print(f"Fastest t2.micro: {fastest_micro}")
        print(f"Fastest t2.large: {fastest_large}")

        # Get the registered instances in each target group
        registered_micro_targets = get_registered_targets(elbv2_client, tg_cluster1_arn)
        registered_large_targets = get_registered_targets(elbv2_client, tg_cluster2_arn)

        print(f"Current registered t2.micro instances: {registered_micro_targets}")
        print(f"Current registered t2.large instances: {registered_large_targets}")

        # Update the target groups for t2.micro and t2.large
        update_target_group(elbv2_client, fastest_micro, tg_cluster1_arn, registered_micro_targets, "t2.micro")
        update_target_group(elbv2_client, fastest_large, tg_cluster2_arn, registered_large_targets, "t2.large")

        # Show the final state of registered instances
        final_micro_targets = get_registered_targets(elbv2_client, tg_cluster1_arn)
        final_large_targets = get_registered_targets(elbv2_client, tg_cluster2_arn)

        print(f"Final registered t2.micro instances: {final_micro_targets}")
        print(f"Final registered t2.large instances: {final_large_targets}")

    except Exception as e:
        print(f"Error updating target groups: {e}")


def main():
    try:
        # Initialize EC2 and ELB clients
        ec2_client = boto3.client('ec2')
        elbv2_client = boto3.client('elbv2')

        # Define essential AWS configuration
        vpc_id = get_vpc_id(ec2_client)
        image_id = 'ami-0e86e20dae9224db8'

        # Get key pair, security group, and subnets
        key_name = get_key_pair(ec2_client)
        security_group_id = get_security_group(ec2_client, vpc_id)
        subnet_ids = get_subnet(ec2_client, vpc_id)

        # Launch EC2 instances for each cluster
        print("Launching EC2 instances...")
        instances_cluster1 = launch_ec2_instances(
            ec2_client, image_id, 't2.micro', key_name, security_group_id, subnet_ids[0], 4
        )
        instances_cluster2 = launch_ec2_instances(
            ec2_client, image_id, 't2.large', key_name, security_group_id, subnet_ids[1], 4
        )

        # Wait for all instances to be in "running" state and collect instance details
        instance_ips = []
        instance_ids = []
        for instance in instances_cluster1 + instances_cluster2:
            instance.wait_until_running()
            instance.reload()  # Reload instance attributes to get updated info
            instance_ips.append(instance.public_ip_address)
            instance_ids.append(instance.id)

        # Print the public IPs of the launched instances
        print("Public IPs of instances:", instance_ips)

        # Wait for CloudWatch metrics to stabilize before determining fastest instances
        print("Waiting for CloudWatch metrics to gather...")
        time.sleep(60)  # Optional wait time to allow metrics to gather

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
        register_to_target_groups(elbv2_client, tg_cluster1_arn, [instance.id for instance in instances_cluster1])
        register_to_target_groups(elbv2_client, tg_cluster2_arn, [instance.id for instance in instances_cluster2])

        # Create listener for load balancer
        create_listener(elbv2_client, lb_arn, tg_cluster1_arn, tg_cluster2_arn)
        time.sleep(180)  # Wait for everything to stabilize and CloudWatch to gather data

        # Now check for the fastest instances
        fastest_micro, fastest_large = load_fastest_instances(instance_ids, ec2_client, tg_cluster1_arn, tg_cluster2_arn)

        if fastest_micro and fastest_large:
            print(f"Fastest t2.micro instance: {fastest_micro}")
            print(f"Fastest t2.large instance: {fastest_large}")

            # Update target groups with the fastest instances
            update_target_groups(elbv2_client, fastest_micro, fastest_large, tg_cluster1_arn, tg_cluster2_arn)
        else:
            print("Unable to retrieve the fastest instances. Retrying...")

        # Periodically check for the fastest instances in an infinite loop
        while True:
            fastest_micro, fastest_large = load_fastest_instances(instance_ids, ec2_client, tg_cluster1_arn, tg_cluster2_arn)

            if fastest_micro and fastest_large:
                # Update target groups with the fastest instances
                update_target_groups(elbv2_client, fastest_micro, fastest_large, tg_cluster1_arn, tg_cluster2_arn)
            else:
                print("Unable to retrieve the fastest instances. Retrying...")
                time.sleep(10)

            time.sleep(60)  # Check every 60 seconds

    except Exception as e:
        print(f"Error during execution: {e}")


# Register instances to target groups
def register_to_target_groups(elbv2_client, target_group_arn, instance_ids):
    """
    Registers instances to a target group.
    """
    register_targets(elbv2_client, target_group_arn, instance_ids)


def load_fastest_instances(instance_ids, ec2_client, tg_micro_arn, tg_large_arn, retries=5, wait_time=30):
    """
    Determine the fastest instances based on CloudWatch metrics (CPU utilization).
    Args:
        instance_ids: List of EC2 instance IDs to evaluate.
        ec2_client: boto3 EC2 client to get instance types.
        tg_micro_arn: ARN for the target group for t2.micro instances.
        tg_large_arn: ARN for the target group for t2.large instances.
        retries: Number of retries in case no data is available.
        wait_time: Seconds to wait between retries.
    Returns:
        Two dictionaries containing instance ID and target group ARN for the fastest t2.micro and t2.large instances.
    """
    for attempt in range(retries):
        micro_instances = []
        large_instances = []

        # Fetch CPU utilization for each instance
        for instance_id in instance_ids:
            cpu_utilization = get_instance_metrics(instance_id)

            if cpu_utilization is not None:
                # Determine the instance type by describing the instance
                try:
                    instance_desc = ec2_client.describe_instances(InstanceIds=[instance_id])
                    instance_type = instance_desc['Reservations'][0]['Instances'][0]['InstanceType']
                except Exception as e:
                    print(f"Error describing instance {instance_id}: {e}")
                    continue

                # Separate instances based on type
                if instance_type == 't2.micro':
                    micro_instances.append((instance_id, cpu_utilization))
                elif instance_type == 't2.large':
                    large_instances.append((instance_id, cpu_utilization))
                else:
                    print(f"Unknown instance type {instance_type} for instance {instance_id}")

        # Ensure there are enough instances with available metrics
        if micro_instances and large_instances:
            # Sort instances by lowest CPU utilization (fastest)
            micro_instances.sort(key=lambda x: x[1])
            large_instances.sort(key=lambda x: x[1])

            # Return the fastest t2.micro and t2.large instances
            fastest_micro = {
                'InstanceId': micro_instances[0][0],
                'TargetGroupArn': tg_micro_arn  # Dynamically provided target group ARN for t2.micro
            }

            fastest_large = {
                'InstanceId': large_instances[0][0],
                'TargetGroupArn': tg_large_arn  # Dynamically provided target group ARN for t2.large
            }

            return fastest_micro, fastest_large
        else:
            print(f"Not enough metrics data yet. Retrying {retries - attempt - 1} more times...")
            time.sleep(wait_time)  # Wait for CloudWatch to gather data

    print("No sufficient CloudWatch data available after retries.")
    return None, None

if __name__ == "__main__":
    main()

