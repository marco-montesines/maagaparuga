# Root Terragrunt config — shared by staging + production (each `include`s this).
#
# Everything sensitive comes from environment variables, never from a committed
# file:
#   HCLOUD_TOKEN                              Hetzner token (project-scoped)
#   AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY S3 key for the state bucket
#                                             (a Backblaze B2 app key OR a
#                                             DigitalOcean Spaces key)
#   TG_STATE_BUCKET / TG_STATE_ENDPOINT / TG_STATE_REGION   where state lives
#
# For a quick local demo with no remote bucket, comment out the `remote_state`
# block below — Terragrunt then keeps state locally in .terragrunt-cache (gitignored).

# ---------------------------------------------------------------------------
# Remote state on an S3-COMPATIBLE bucket (Backblaze B2 or DigitalOcean Spaces).
# Native S3 lockfile locking (Terraform >= 1.10) — no DynamoDB table needed.
# The offsite S3 you already have doubles as the state store; separate provider
# from Hetzner keeps state recoverable even if the Hetzner project is lost.
# ---------------------------------------------------------------------------
remote_state {
  backend = "s3"
  generate = {
    path      = "backend.tf"
    if_exists = "overwrite_terragrunt"
  }
  config = {
    bucket = get_env("TG_STATE_BUCKET", "bgg-iac-tfstate")
    key    = "${path_relative_to_include()}/terraform.tfstate"
    region = get_env("TG_STATE_REGION", "us-east-1")
    endpoints = {
      s3 = get_env("TG_STATE_ENDPOINT", "https://s3.us-west-004.backblazeb2.com")
    }
    # NOTE: no state locking. Terraform's S3-native lockfile needs a conditional
    # PutObject (If-None-Match) that Backblaze B2 does NOT implement (it returns
    # 501 NotImplemented), and B2 has no DynamoDB equivalent. Fine for a solo
    # operator; enable B2 bucket VERSIONING so a bad apply can be rolled back.
    # (If you switch state to DigitalOcean Spaces later, test use_lockfile there.)

    # Non-AWS S3 (B2 / DO Spaces) needs these skips + no checksum trailers.
    skip_credentials_validation = true
    skip_region_validation      = true
    skip_requesting_account_id  = true
    skip_metadata_api_check     = true
    skip_s3_checksum            = true
    use_path_style              = true
  }
}

# ---------------------------------------------------------------------------
# Generate the Hetzner provider. Token resolves from the hcloud_token variable
# (a gitignored *.tfvars) or, if that is empty, the HCLOUD_TOKEN env var.
# ---------------------------------------------------------------------------
generate "provider" {
  path      = "provider.tf"
  if_exists = "overwrite_terragrunt"
  contents  = <<-EOF
    provider "hcloud" {
      token = var.hcloud_token != "" ? var.hcloud_token : null
    }
  EOF
}

# Point every environment at the cluster module.
terraform {
  source = "${get_repo_root()}/infra/modules//cluster"
}

# Inputs shared by all environments (env-specific ones live in each child).
inputs = {
  project = "bgg-iac"
}
