# -*- coding: utf-8 -*-

import aws_cdk as cdk
from lib.stages.dev import DevStage

project_name = "fastapi-ecs-training-cluster"
app = cdk.App()
tags = [("project-name", project_name), ("acimate-app-id", "APP-999")]

dev_stage = DevStage(
    app,
    "dev",
    env=cdk.Environment(account="707690426194", region="us-east-1"),
    project_name=project_name,
    app_tags=tags,
)

[cdk.Tags.of(stage).add(tag[0], tag[1]) for tag in tags for stage in [dev_stage]]

app.synth()
