import time
import boto3
import requests

cloudwatch = boto3.client('cloudwatch', region_name='us-east-1')
ec2_client = boto3.client('ec2', region_name='us-east-1')

def get_ips(instance_type):
    try:
        response = ec2_client.describe_instances(
            Filters=[
                {
                    'Name': 'instance-type',
                    'Values': [instance_type]
                },
                {
                    'Name': 'instance-state-name',
                    'Values': ['running']
                }
            ]
        )

        instance_data = []
        for reservation in response['Reservations']:
            for instance in reservation['Instances']:
                instance_data.append({
                    'InstanceId': instance['InstanceId'],
                    'PublicIpAddress': instance['PublicIpAddress']
                })

        return instance_data
    except Exception as e:
        print(f"Error retrieving instance IPs: {e}")
        return []


def save_fastest_instances(fastest_micro, fastest_large):
    with open("fastest_instances.txt", "w") as f:
        if fastest_micro:
            #print(f"Fastest t2.micro instance: {fastest_micro['InstanceId']} with IP: {fastest_micro['PublicIpAddress']}")
            f.write(
                f"Fastest t2.micro instance: {fastest_micro['InstanceId']} with IP: {fastest_micro['PublicIpAddress']}\n")
        else:
            f.write("No fastest t2.micro instance found\n")

        if fastest_large:
            #print( f"Fastest t2.large instance: {fastest_large['InstanceId']} with IP: {fastest_large['PublicIpAddress']}")
            f.write(
                f"Fastest t2.large instance: {fastest_large['InstanceId']} with IP: {fastest_large['PublicIpAddress']}\n")
        else:
            f.write("No fastest t2.large instance found\n")


def check_instance_response_time():
    fastest_micro_instance = None
    fastest_large_instance = None
    fastest_micro_time = float('inf')
    fastest_large_time = float('inf')

    for instance_name, instance_data in instance_endpoints.items():
        try:
            start_time = time.time()  # Start the timer
            response = requests.get(instance_data['url'])
            response.raise_for_status()  # Raise exception if the request fails
            process_time = time.time() - start_time  # Calculate the response time

            print(f"Instance {instance_name} responded in {process_time:.4f} seconds")

            # Check fastest t2.micro instance
            #print(f"{'t2.micro' == instance_name} {process_time < fastest_micro_time}")
            if 'cluster1' in instance_name and process_time < fastest_micro_time:
                fastest_micro_time = process_time
                fastest_micro_instance = instance_data  # Save instance data

            # Check fastest t2.large instance
            #print(f"{'t2.large' == instance_name} {process_time < fastest_large_time}")
            if 'cluster2' in instance_name and process_time < fastest_large_time:
                fastest_large_time = process_time
                fastest_large_instance = instance_data  # Save instance data

        except Exception as e:
            print(f"Error checking {instance_name}: {e}")

    # Save the fastest instances to the file
    save_fastest_instances(fastest_micro_instance, fastest_large_instance)


cluster1_instances = get_ips('t2.micro')
cluster2_instances = get_ips('t2.large')

print(f"Cluster 1 (t2.micro) : {cluster1_instances}")
print(f"Cluster 2 (t2.large) : {cluster2_instances}")

instance_endpoints = {}
for idx, instance in enumerate(cluster1_instances):
    instance_endpoints[f"cluster1-instance{idx + 1}"] = {
        'InstanceId': instance['InstanceId'],
        'PublicIpAddress': instance['PublicIpAddress'],
        'url': f"http://{instance['PublicIpAddress']}:8000/"
    }

for idx, instance in enumerate(cluster2_instances):
    instance_endpoints[f"cluster2-instance{idx + 1}"] = {
        'InstanceId': instance['InstanceId'],
        'PublicIpAddress': instance['PublicIpAddress'],
        'url': f"http://{instance['PublicIpAddress']}:8000/"
    }

while True:
    check_instance_response_time()
    time.sleep(5)
