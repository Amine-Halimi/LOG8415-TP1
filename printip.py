
# This is just a help file that helps finding the public IPs of running instances so we don't have to look to the web dashboard and connect immediately
# Created entirely by ChatGPT

import boto3

def print_running_instance_ips():
    session = boto3.Session()
    ec2_client = session.client('ec2')

    response = ec2_client.describe_instances()

    for reservation in response['Reservations']:
        for instance in reservation['Instances']:
            if instance['State']['Name'] == 'running':
                public_ip = instance.get('PublicIpAddress')
                instance_id = instance['InstanceId']
                if public_ip:
                    print(f"Instance ID: {instance_id}, Public IP: {public_ip}")
                else:
                    print(f"Instance ID: {instance_id} does not have a public IP.")

if __name__ == "__main__":
    print_running_instance_ips()
