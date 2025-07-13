# Lambda function for ECS control
resource "aws_lambda_function" "ecs_controller" {
  filename         = "ecs_controller.zip"
  function_name    = "${var.project_name}-ecs-controller"
  role            = aws_iam_role.lambda_execution.arn
  handler         = "index.handler"
  runtime         = "nodejs18.x"
  timeout         = 30

  environment {
    variables = {
      CLUSTER_NAME        = aws_ecs_cluster.main.name
      TASK_DEFINITION     = aws_ecs_task_definition.app.arn
      SUBNET_IDS          = join(",", aws_subnet.public[*].id)
      SECURITY_GROUP_ID   = aws_security_group.ecs.id
      TARGET_GROUP_ARN_8081 = aws_lb_target_group.app_8081.arn
      TARGET_GROUP_ARN_5173 = aws_lb_target_group.app_5173.arn
    }
  }

  depends_on = [data.archive_file.lambda_zip]
}

# API Gateway
resource "aws_api_gateway_rest_api" "main" {
  name = "${var.project_name}-api"
}

resource "aws_api_gateway_resource" "ecs" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_rest_api.main.root_resource_id
  path_part   = "ecs"
}

resource "aws_api_gateway_method" "ecs_post" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.ecs.id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_method" "ecs_get" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.ecs.id
  http_method   = "GET"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "ecs_post" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.ecs.id
  http_method = aws_api_gateway_method.ecs_post.http_method

  integration_http_method = "POST"
  type                   = "AWS_PROXY"
  uri                    = aws_lambda_function.ecs_controller.invoke_arn
}

resource "aws_api_gateway_integration" "ecs_get" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.ecs.id
  http_method = aws_api_gateway_method.ecs_get.http_method

  integration_http_method = "POST"
  type                   = "AWS_PROXY"
  uri                    = aws_lambda_function.ecs_controller.invoke_arn
}

# CORS
resource "aws_api_gateway_method" "ecs_options" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.ecs.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "ecs_options" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.ecs.id
  http_method = aws_api_gateway_method.ecs_options.http_method

  type = "MOCK"
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "ecs_options" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.ecs.id
  http_method = aws_api_gateway_method.ecs_options.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "ecs_options" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.ecs.id
  http_method = aws_api_gateway_method.ecs_options.http_method
  status_code = aws_api_gateway_method_response.ecs_options.status_code

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,POST,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

resource "aws_api_gateway_deployment" "main" {
  depends_on = [
    aws_api_gateway_integration.ecs_post,
    aws_api_gateway_integration.ecs_get,
    aws_api_gateway_integration.ecs_options
  ]

  rest_api_id = aws_api_gateway_rest_api.main.id
}

resource "aws_api_gateway_stage" "prod" {
  deployment_id = aws_api_gateway_deployment.main.id
  rest_api_id   = aws_api_gateway_rest_api.main.id
  stage_name    = "prod"
}

resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ecs_controller.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.main.execution_arn}/*/*"
}

# Lambda function code
data "archive_file" "lambda_zip" {
  type        = "zip"
  output_path = "ecs_controller.zip"
  source {
    content = templatefile("${path.module}/lambda/ecs_controller.js", {
      cluster_name = aws_ecs_cluster.main.name
    })
    filename = "index.js"
  }
}