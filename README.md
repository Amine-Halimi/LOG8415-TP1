# LOG8415-TP1
This is where we will put our code and scripts.

Ok here is a guide for what I made so far.
Once you start your lab, you have to change your credentials in ~/.aws/credentials to AWS CLI in AWS details next to start lab. 

Change your AMI ID in start.py

Then you have to create a security group (it is not included in code) with Inbound rules:
Type - Protocol - Post range - Source : 
SSH - TCP - 22 -  security group id &&
SSH - TCP - 22 -  0.0.0.0/0 &&
CustomTCP - TCP - 8000 - MyLocalIP &&
CustomTCP - TCP - 8000 - 0.0.0.0/0

Then  create two subnets with different Availability Zone (may be by default created)

Now start start.py

Execute printip.py to show all IPs of instances

Now wait 30sec then
curl http://<IP of instance>:8000/clusterX
and it should answer request

Check the DNS of the load balancer in the AWS website, wait until the state is "Active" and try then
curl http://<DNS of load balancer>:8000/
and it should answer request

At the end execute terminate.py to terminate instances
