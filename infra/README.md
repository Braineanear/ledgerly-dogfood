# Infrastructure

This directory contains the Terraform foundation for future Google Cloud
infrastructure. It configures the Google provider and accepts a project ID and
region, but intentionally creates no resources.

## Configuration

Set the Google Cloud project ID before planning future infrastructure:

```sh
export TF_VAR_project_id="your-project-id"
```

The region defaults to `us-central1`. Override it when needed:

```sh
export TF_VAR_region="your-region"
```

## Validation

Validate formatting and configuration without configuring remote state:

```sh
make infra-validate
```

This command initializes Terraform with `-backend=false`, then validates the
configuration. It does not create, change, or destroy cloud resources.

## Deferred decisions

Remote state backend configuration, deployment workflows, credentials, and
Google Cloud resources are intentionally deferred. Do not add credentials to
Terraform files or commit Terraform state.
