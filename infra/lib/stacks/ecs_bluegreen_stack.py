from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    aws_ec2 as ec2,
    aws_ecr as ecr,
    aws_ecs as ecs,
    aws_elasticloadbalancingv2 as elbv2,
    aws_iam as iam,
    aws_logs as logs,
    aws_lambda as _lambda,
    aws_codedeploy as codedeploy,
    CfnOutput,
)
from constructs import Construct


class EcsBlueGreenStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Networking
        vpc = ec2.Vpc(self, "Vpc", max_azs=2, nat_gateways=1)

        # ECR repo for your service image
        repo = ecr.Repository(
            self,
            "AppRepo",
            image_scan_on_push=True,
            removal_policy=RemovalPolicy.RETAIN,
            lifecycle_rules=[ecr.LifecycleRule(max_image_count=50)],
            repository_name="ecs-bluegreen-app",
        )

        # ECS cluster
        cluster = ecs.Cluster(self, "Cluster", vpc=vpc)

        # Task definition
        task_role = iam.Role(
            self,
            "TaskRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
        )
        execution_role = iam.Role(
            self,
            "ExecutionRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AmazonECSTaskExecutionRolePolicy"
                )
            ],
        )

        log_group = logs.LogGroup(
            self,
            "AppLogGroup",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.DESTROY,
        )

        task_def = ecs.FargateTaskDefinition(
            self,
            "TaskDef",
            cpu=512,
            memory_limit_mib=1024,
            task_role=task_role,
            execution_role=execution_role,
        )

        container = task_def.add_container(
            "AppContainer",
            image=ecs.ContainerImage.from_registry(
                # initial bootstrap image; your pipeline will push to ECR and register new task defs
                "public.ecr.aws/nginx/nginx:stable"
            ),
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="app", log_group=log_group
            ),
            environment={
                "ENV": "prod",
            },
            health_check=ecs.HealthCheck(
                command=["CMD-SHELL", "curl -f http://localhost/ || exit 1"],
                interval=Duration.seconds(30),
                timeout=Duration.seconds(5),
                retries=3,
                start_period=Duration.seconds(10),
            ),
        )
        container_port = 80
        container.add_port_mappings(ecs.PortMapping(container_port=container_port))

        # Security groups
        alb_sg = ec2.SecurityGroup(self, "AlbSG", vpc=vpc, allow_all_outbound=True)
        alb_sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(80), "HTTP")
        alb_sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(9001), "Test listener")

        svc_sg = ec2.SecurityGroup(self, "ServiceSG", vpc=vpc, allow_all_outbound=True)
        svc_sg.add_ingress_rule(
            alb_sg, ec2.Port.tcp(container_port), "Allow ALB to reach tasks"
        )

        # ALB with listeners (prod + test)
        alb = elbv2.ApplicationLoadBalancer(
            self, "Alb", vpc=vpc, internet_facing=True, security_group=alb_sg
        )

        blue_tg = elbv2.ApplicationTargetGroup(
            self,
            "BlueTG",
            vpc=vpc,
            target_type=elbv2.TargetType.IP,
            port=container_port,
            protocol=elbv2.ApplicationProtocol.HTTP,
            health_check=elbv2.HealthCheck(
                path="/", healthy_http_codes="200-399", interval=Duration.seconds(20)
            ),
        )

        green_tg = elbv2.ApplicationTargetGroup(
            self,
            "GreenTG",
            vpc=vpc,
            target_type=elbv2.TargetType.IP,
            port=container_port,
            protocol=elbv2.ApplicationProtocol.HTTP,
            health_check=elbv2.HealthCheck(
                path="/", healthy_http_codes="200-399", interval=Duration.seconds(20)
            ),
        )

        prod_listener = alb.add_listener(
            "ProdListener", port=80, open=True, default_target_groups=[blue_tg]
        )
        test_listener = alb.add_listener(
            "TestListener", port=9001, protocol=elbv2.ApplicationProtocol.HTTP, open=True, default_target_groups=[green_tg]
        )

        # Fargate service with CodeDeploy controller
        service = ecs.FargateService(
            self,
            "Service",
            cluster=cluster,
            task_definition=task_def,
            desired_count=2,
            assign_public_ip=True,
            security_groups=[svc_sg],
            deployment_controller=ecs.DeploymentController(
                type=ecs.DeploymentControllerType.CODE_DEPLOY
            ),
            circuit_breaker=None,  # CodeDeploy handles deployment lifecycle
            health_check_grace_period=Duration.seconds(60),
        )

        # Register BLUE target group to the service (GREEN will be used by CodeDeploy during deployments)
        #service.attach_to_application_target_group(blue_tg)

        # Grant ALB to reach service tasks
        blue_tg.add_target(service)

        # CodeDeploy IAM role
        codedeploy_role = iam.Role(
            self,
            "CodeDeployRole",
            assumed_by=iam.ServicePrincipal("codedeploy.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AWSCodeDeployRoleForECS"
                )
            ],
        )

        # Lambda hook to validate test traffic (AfterAllowTestTraffic)
        pre_hook = _lambda.Function(
            self,
            "AfterAllowTestTrafficHook",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="pre_traffic_hook.handler",
            code=_lambda.Code.from_asset("../src/lambda"),
            memory_size=256,
            timeout=Duration.seconds(60),
            environment={
                "TEST_URL": f"http://{alb.load_balancer_dns_name}:9001/",
            },
        )

        # Allow CodeDeploy service to invoke the hook
        pre_hook.add_permission(
            "AllowCodeDeployInvoke",
            principal=iam.ServicePrincipal("codedeploy.amazonaws.com"),
            action="lambda:InvokeFunction",
        )

        # CodeDeploy ECS Application
        cd_app = codedeploy.CfnApplication(
            self, "EcsCodeDeployApp", compute_platform="ECS", application_name="ecs-bluegreen-app"
        )

        # CodeDeploy Deployment Group (BLUE/GREEN)
        cd_group = codedeploy.CfnDeploymentGroup(
            self,
            "EcsDeploymentGroup",
            application_name=cd_app.application_name,
            service_role_arn=codedeploy_role.role_arn,
            deployment_config_name="CodeDeployDefault.ECSLinear10PercentEvery1Minutes",
            deployment_style=codedeploy.CfnDeploymentGroup.DeploymentStyleProperty(
                deployment_option="WITH_TRAFFIC_CONTROL", deployment_type="BLUE_GREEN"
            ),
            blue_green_deployment_configuration=codedeploy.CfnDeploymentGroup.BlueGreenDeploymentConfigurationProperty(
                terminate_blue_instances_on_deployment_success=codedeploy.CfnDeploymentGroup.BlueInstanceTerminationOptionProperty(
                    action="TERMINATE", termination_wait_time_in_minutes=5
                ),
                deployment_ready_option=codedeploy.CfnDeploymentGroup.DeploymentReadyOptionProperty(
                    action_on_timeout="CONTINUE_DEPLOYMENT", wait_time_in_minutes=0
                ),                
            ),
            auto_rollback_configuration=codedeploy.CfnDeploymentGroup.AutoRollbackConfigurationProperty(
                enabled=True,
                events=[
                    "DEPLOYMENT_FAILURE",
                    "DEPLOYMENT_STOP_ON_ALARM",
                    "DEPLOYMENT_STOP_ON_REQUEST",
                ],
            ),
            ecs_services=[
                codedeploy.CfnDeploymentGroup.ECSServiceProperty(
                    service_name=service.service_name, cluster_name=cluster.cluster_name
                )
            ],
            load_balancer_info=codedeploy.CfnDeploymentGroup.LoadBalancerInfoProperty(
                target_group_pair_info_list=[
                    codedeploy.CfnDeploymentGroup.TargetGroupPairInfoProperty(
                        prod_traffic_route=codedeploy.CfnDeploymentGroup.TrafficRouteProperty(
                            listener_arns=[prod_listener.listener_arn]
                        ),
                        test_traffic_route=codedeploy.CfnDeploymentGroup.TrafficRouteProperty(
                            listener_arns=[test_listener.listener_arn]
                        ),
                        target_groups=[
                            codedeploy.CfnDeploymentGroup.TargetGroupInfoProperty(
                                name=blue_tg.target_group_name
                            ),
                            codedeploy.CfnDeploymentGroup.TargetGroupInfoProperty(
                                name=green_tg.target_group_name
                            ),
                        ],
                    )
                ]
            ),
        )

        # Useful outputs for pipeline wiring
        CfnOutput(self, "EcrRepositoryUri", value=repo.repository_uri)
        CfnOutput(self, "ClusterName", value=cluster.cluster_name)
        CfnOutput(self, "ServiceName", value=service.service_name)
        CfnOutput(self, "AlbDns", value=alb.load_balancer_dns_name)
        CfnOutput(self, "CodeDeployApplicationName", value=cd_app.application_name)
        CfnOutput(self, "CodeDeployDeploymentGroupName", value=cd_group.ref)
        CfnOutput(self, "PreTrafficHookName", value=pre_hook.function_name)
        CfnOutput(self, "ContainerName", value=container.container_name)
        CfnOutput(self, "ContainerPort", value=str(container_port))
        CfnOutput(self, "ECSTaskRole", value=str(task_role))
        CfnOutput(self, "ECSExecutionRole", value=str(execution_role))
        