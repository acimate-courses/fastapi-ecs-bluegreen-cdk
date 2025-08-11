# -*- coding: utf-8 -*-
from aws_cdk import Environment, Stage
from constructs import Construct
from lib.stacks.ecs_bluegreen_stack import EcsBlueGreenStack



class DevStage(Stage):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        env: Environment,
        project_name: str,
        app_tags: list[tuple[str, str]],
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        deploy_environment = "dev"

        ecs_bg_stack = EcsBlueGreenStack(
            self,
            f"{project_name}-{env.region}-ecs-blue-green",            
            env=Environment(account=env.account, region=env.region),
        )
        