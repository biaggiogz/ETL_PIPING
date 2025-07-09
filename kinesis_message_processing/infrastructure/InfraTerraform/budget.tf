resource "aws_budgets_budget" "realtime_budget" {
  name              = "${var.app_name_react}-monthly-budget"
  budget_type       = "COST"
  time_unit         = "MONTHLY"
  time_period_start = formatdate("YYYY-MM-01_00:00", timestamp())
  
  # Set your monthly budget limit in USD
  limit_amount      = "100"
  limit_unit        = "USD"

  # Configure notifications at 80% and 100% of budget
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = ["gutierrezauntuam@gmail.com"]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = ["gutierrezauntuam@gmail.com"]
  }

  # Track by service
  cost_filter {
    name = "Service"
    values = [
      "Amazon Elastic Container Service",
      "Amazon CloudFront",
      "Amazon Simple Storage Service",
      "Amazon EC2 Container Registry",
      "AmazonCloudWatch",
      "AWS CodeBuild",
      "AWS CodePipeline",
      "Elastic Load Balancing"
    ]
  }

  # Use app_name tag to track all resources with this tag
  cost_filter {
    name = "TagKeyValue"
    values = [
      "Name$${var.app_name}"
    ]
  }

  cost_types {
    include_credit             = false
    include_discount           = true
    include_other_subscription = true
    include_recurring          = true
    include_refund             = false
    include_subscription       = true
    include_tax                = true
    include_upfront            = true
    use_blended                = false
  }
}
# CloudWatch Dashboard for daily cost monitoring
resource "aws_cloudwatch_dashboard" "cost_dashboard" {
  dashboard_name = "${var.app_name_react}-cost-dashboard"
  
  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 24
        height = 6
        properties = {
          metrics = [
            ["AWS/Billing", "EstimatedCharges", "ServiceName", "AmazonECS", { "period": 86400, "stat": "Maximum" }],
            ["AWS/Billing", "EstimatedCharges", "ServiceName", "AmazonCloudFront", { "period": 86400, "stat": "Maximum" }],
            ["AWS/Billing", "EstimatedCharges", "ServiceName", "AmazonS3", { "period": 86400, "stat": "Maximum" }],
            ["AWS/Billing", "EstimatedCharges", "ServiceName", "AmazonECR", { "period": 86400, "stat": "Maximum" }],
            ["AWS/Billing", "EstimatedCharges", "ServiceName", "AmazonCloudWatch", { "period": 86400, "stat": "Maximum" }],
            ["AWS/Billing", "EstimatedCharges", "ServiceName", "CodeBuild", { "period": 86400, "stat": "Maximum" }],
            ["AWS/Billing", "EstimatedCharges", "ServiceName", "CodePipeline", { "period": 86400, "stat": "Maximum" }],
            ["AWS/Billing", "EstimatedCharges", "ServiceName", "ElasticLoadBalancing", { "period": 86400, "stat": "Maximum" }]
          ],
          view = "timeSeries",
          stacked = false,
          region = data.aws_region.current.name,
          title = "Daily Estimated Charges by Service",
          period = 86400,
          yAxis = {
            left = {
              min = 0
            }
          }
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 24
        height = 6
        properties = {
          metrics = [
            ["AWS/Billing", "EstimatedCharges", "Currency", "USD", { "period": 86400, "stat": "Maximum", "label": "Total Estimated Charges" }]
          ],
          view = "timeSeries",
          stacked = false,
          region = data.aws_region.current.name,
          title = "Total Daily Estimated Charges",
          period = 86400,
          annotations = {
            horizontal = [
              {
                value = 100,
                label = "Budget Limit ($100)",
                color = "#ff0000"
              }
            ]
          },
          yAxis = {
            left = {
              min = 0
            }
          }
        }
      }
    ]
  })
}