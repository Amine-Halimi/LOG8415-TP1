
# This is just a help file which helps finding the public IPs of running instances so we dont have to look to web dashboard and connect immediately
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
                instance_type = instance['InstanceType']  

                if public_ip:
                    print(f"Instance ID: {instance_id}, Public IP: {public_ip}, Instance Type: {instance_type}")
                else:
                    print(f"Instance ID: {instance_id}, Instance Type: {instance_type} does not have a public IP.")


if __name__ == "__main__":
    print_running_instance_ips()
