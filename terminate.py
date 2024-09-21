import boto3
import os

def remove_key_file():
    # Get path of key file
    key_file_path = os.path.expanduser("~/.aws/tp1.pem")

    try:
        os.remove(key_file_path)
        print(f"Key file '{key_file_path}' has been deleted successfully.")
    except FileNotFoundError:
        print(f"Error: The file '{key_file_path}' does not exist.")
    except PermissionError:
        print(f"Error: Permission denied when trying to delete '{key_file_path}'.")
    except Exception as e:
        print(f"An error occurred: {e}")

def terminate_running_instances():
    session = boto3.Session()
    ec2 = session.resource('ec2')

    # Get running instances and their IDs
    running_instances = ec2.instances.filter(Filters=[{'Name': 'instance-state-name', 'Values': ['running']}])
    instance_ids = [instance.id for instance in running_instances]

    if not instance_ids:
        print("No running instances found to terminate.")
    else:
        # Terminate running instances
        ec2.instances.filter(InstanceIds=instance_ids).terminate()
        print(f"Terminating instances: {instance_ids}")

if __name__ == "__main__":
    terminate_running_instances()
    remove_key_file()
