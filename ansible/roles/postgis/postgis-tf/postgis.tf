terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
    null = {
      source  = "hashicorp/null"
      version = "~> 3.2"
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

resource "aws_rds_cluster" "n7m" {
  cluster_identifier          = "n7m-cluster"
  engine                      = "aurora-postgresql"
  database_name               = "n7m"
  master_username             = "postgres"
  manage_master_user_password = true
  backup_retention_period     = 5
  preferred_backup_window     = "05:00-07:00"
  skip_final_snapshot         = true
}

resource "aws_rds_cluster_instance" "n7m_instances" {
  count               = 1
  identifier          = "n7m-instance-${count.index + 1}"
  cluster_identifier  = aws_rds_cluster.n7m.id
  instance_class      = "db.t4g.medium"
  engine              = aws_rds_cluster.n7m.engine
  engine_version      = aws_rds_cluster.n7m.engine_version
  publicly_accessible = true
}

