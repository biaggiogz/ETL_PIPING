
output "azs" {
  description = "A list of availability zones for the region of the current AWS profile."
  value       = data.aws_availability_zones.available.names

}
