# fastapi-ecs-bluegreen-cdk
This demonstrate blue green deployment for ECS based container apps.
# Perform following manually to test blue-green deployment
1. change in main.py under app folder
2. Update Task role and execution role manually from ECS- Task console once deployment is done.
3. update appspec.yml file task definition version
4. update loggroup name - created newly in the task definition.json
