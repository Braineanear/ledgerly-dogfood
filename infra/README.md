# Infrastructure

This directory contains the Terraform configuration for Google Cloud
infrastructure. It configures the Google provider, a partial GCS state
backend, and one Cloud Storage bucket.

## Resources

- `google_storage_bucket.main`: named by the `bucket_name` variable and placed
  in `region`. It enforces uniform bucket-level access and public access
  prevention, enables versioning, and does not set `force_destroy`.

The `bucket_name` output returns the bucket name.

## Configuration

Copy the example files and replace every `REPLACE_ME` placeholder:

```sh
cd infra
cp backend.hcl.example backend.hcl
cp terraform.tfvars.example terraform.tfvars
```

- `backend.hcl` sets the state `bucket` and `prefix` for the backend.
- `terraform.tfvars` sets `project_id` and `bucket_name`.

`REPLACE_ME` is a placeholder only. It is not a valid project ID or bucket
name (bucket names are globally unique, lowercase, and cannot contain
underscores), so planning or applying fails until it is replaced.

The region defaults to `us-central1`. Override it when needed:

```sh
export TF_VAR_region="your-region"
```

Initialize with the backend configuration, since the backend block is empty:

```sh
terraform init -backend-config=backend.hcl
```

## Validation

Validate formatting and configuration without configuring remote state:

```sh
make infra-validate
```

This command initializes Terraform with `-backend=false`, then validates the
configuration. It does not create, change, or destroy cloud resources.

## Deferred decisions

Deployment workflows and credentials are intentionally deferred. Do not add
credentials to Terraform files or commit Terraform state.
