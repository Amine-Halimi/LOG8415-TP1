import boto3

def terminate_running_instances():
    session = boto3.Session()
    ec2 = session.resource('ec2')

    running_instances = ec2.instances.filter(Filters=[{'Name': 'instance-state-name', 'Values': ['running']}])

    instance_ids = [instance.id for instance in running_instances]

    if not instance_ids:
        print("No running instances found to terminate.")
    else:
        ec2.instances.filter(InstanceIds=instance_ids).terminate()
        print(f"Terminating instances: {instance_ids}")

if __name__ == "__main__":
    terminate_running_instances()
