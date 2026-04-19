from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_iam as iam,
    CfnOutput,
)
from constructs import Construct


class ComputeStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        # VPC — single AZ for demo simplicity
        self.vpc = ec2.Vpc(
            self, "CsrVpc",
            vpc_name="csr-vpc",
            max_azs=1,
            nat_gateways=1,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                ),
                ec2.SubnetConfiguration(
                    name="private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24,
                ),
            ],
        )

        # Security group for EC2
        self.ec2_sg = ec2.SecurityGroup(
            self, "Ec2SecurityGroup",
            vpc=self.vpc,
            security_group_name="csr-ec2-sg",
            description="CSR demo EC2: Pebble CA + Nginx",
        )
        # HTTPS from anywhere (Nginx)
        self.ec2_sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(443), "HTTPS Nginx")
        self.ec2_sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(80), "HTTP Nginx")
        # Pebble CA ACME endpoint (internal)
        self.ec2_sg.add_ingress_rule(ec2.Peer.ipv4(self.vpc.vpc_cidr_block), ec2.Port.tcp(14000), "Pebble ACME")
        self.ec2_sg.add_ingress_rule(ec2.Peer.ipv4(self.vpc.vpc_cidr_block), ec2.Port.tcp(15000), "Pebble mgmt")

        # IAM role for EC2 — SSM access so Lambdas can run commands without SSH
        ec2_role = iam.Role(
            self, "Ec2InstanceRole",
            role_name="csr-ec2-role",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonSSMManagedInstanceCore"
                ),
            ],
        )

        # User data — installs Docker, Nginx, Pebble on first boot
        user_data = ec2.UserData.for_linux()
        user_data.add_commands(
            "set -e",
            "yum update -y",
            # Docker
            "amazon-linux-extras install docker -y",
            "systemctl start docker",
            "systemctl enable docker",
            # Docker Compose
            'curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose',
            "chmod +x /usr/local/bin/docker-compose",
            # Nginx
            "amazon-linux-extras install nginx1 -y",
            "systemctl start nginx",
            "systemctl enable nginx",
            # Pull and start Pebble
            "mkdir -p /opt/pebble",
            "cat > /opt/pebble/docker-compose.yml << 'EOF'",
            "version: '3'",
            "services:",
            "  pebble:",
            "    image: letsencrypt/pebble:latest",
            "    ports:",
            "      - '14000:14000'",
            "      - '15000:15000'",
            "    environment:",
            "      - PEBBLE_VA_NOSLEEP=1",
            "      - PEBBLE_VA_ALWAYS_VALID=1",
            "    command: pebble -config /test/config/pebble-config.json",
            "    volumes:",
            "      - /opt/pebble/config:/test/config",
            "EOF",
            "mkdir -p /opt/pebble/config",
            "cat > /opt/pebble/config/pebble-config.json << 'EOF'",
            '{',
            '  "pebble": {',
            '    "listenAddress": "0.0.0.0:14000",',
            '    "managementListenAddress": "0.0.0.0:15000",',
            '    "certificate": "test/certs/localhost/cert.pem",',
            '    "privateKey": "test/certs/localhost/key.pem",',
            '    "httpPort": 5002,',
            '    "tlsPort": 5001,',
            '    "ocspResponderURL": "",',
            '    "externalAccountBindingRequired": false',
            '  }',
            '}',
            "EOF",
            "cd /opt/pebble && docker-compose up -d",
            # Signal SSM that setup is complete
            "echo 'CSR EC2 setup complete' > /var/log/csr-setup.log",
        )

        # EC2 instance (Amazon Linux 2, t3.small for demo)
        self.instance = ec2.Instance(
            self, "CsrDemoInstance",
            instance_type=ec2.InstanceType("t3.small"),
            machine_image=ec2.AmazonLinuxImage(
                generation=ec2.AmazonLinuxGeneration.AMAZON_LINUX_2,
            ),
            vpc=self.vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            security_group=self.ec2_sg,
            role=ec2_role,
            user_data=user_data,
            instance_name="csr-demo-server",
        )

        CfnOutput(self, "InstanceId", value=self.instance.instance_id)
        CfnOutput(self, "InstancePublicIp", value=self.instance.instance_public_ip)
