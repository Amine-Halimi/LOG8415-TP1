# LOG8415-TP1
This is where we will put our code and scripts.

Ok here is a guide for what I made so far.
Once you start your lab, you have to change your credentials in ~/.aws/credentials to AWS CLI in AWS details next to start lab. 

Then you have to create a security group (it is not included in code) with Inbound rules:
Type - Protocol - Post range - Source : 
SSH - TCP - 22 -  security group id &&
SSH - TCP - 22 -  0.0.0.0/0 &&
CustomTCP - TCP - 8000 - MyLocalIP

Then  create two subnets with different Availability Zone (may be by default created)

Now start start.py

Execute printip.py to show all IPs of instances

scp -i ~/.aws/tp1.pem path/to/my_fastapi.py ec2-user@<IP of instance>:~/my_fastapi.py

Now wait cca 30sec then
curl http://<IP of instance>:8000/
and it should answer request

At the end execute terminate.py to terminate instances

The code already contains load balancer and target groups, but it doesnt do anything yet
