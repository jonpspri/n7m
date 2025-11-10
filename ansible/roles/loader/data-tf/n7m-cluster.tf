terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
  required_version = "~> 1.10.6"
}

provider "aws" {
  region = "eu-west-1"
}

variable "n7m_region" {
  type        = string
  default     = "monaco"
  description = "Region to load into Nominatim cluster"
}

resource "aws_efs_file_system" "n7m_data" {
  lifecycle_policy {
    transition_to_ia = "AFTER_7_DAYS"
  }
}

resource "aws_ecs_task_definition" "n7m-download-wiki-and-grid" {
  family                   = "n7m-download-wiki-and-grid"
  requires_compatibilities = ["FARGATE"]
  container_definitions = jsonencode([
    {
      name   = "feed"
      image  = "ghcr.io/jonpspri/n7m-feed:latest" # TODO: Parameterize
      cpu    = 10
      memory = 256
      mountPoints = [
        {
          sourceVolume  = "data"
          containerPath = "/data"
          readOnly      = false
        }
      ]
    command = ["download", "--wiki", "--grid"] }
  ])
  volume {
    name = "data"
    efs_volume_configuration {
      file_system_id = aws_efs_file_system.n7m_data.id
    }
  }
}

resource "aws_ecs_cluster" "n7m-ecs-cluster" {
  name = "n7m-ecs-cluster"
}

resource "aws_ecs_task_definition" "n7m-download-owm" {
  family                   = "n7m-download-osm"
  requires_compatibilities = ["FARGATE"]
  container_definitions = jsonencode([
    {
      name   = "openmaptiles-tools"
      image  = "openmaptiles/openmaptiles-tools:latest"
      cpu    = 10
      memory = 256
      mountPoints = [
        {
          sourceVolume  = "data"
          containerPath = "/tileset"
          readOnly      = false
        }
      ]

      command = ["download-owm", var.n7m_region]
    }
  ])
  volume {
    name = "data"
    efs_volume_configuration {
      file_system_id = aws_efs_file_system.n7m_data.id
    }
  }
}
