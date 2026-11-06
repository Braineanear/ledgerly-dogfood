# Infrastructure

This directory contains the Terraform configuration for Google Cloud
infrastructure. It configures the Google provider, a partial GCS state
backend, API enablement, a VPC module, a Cloud SQL module, and one Cloud
Storage bucket.

## Layout

- `main.tf`, `variables.tf`, `outputs.tf`, `versions.tf`: the root module.
- `modules/vpc`: network, subnet and private service access.
- `modules/cloudsql`: Postgres instance, database and user.

Each module has its own `main.tf`, `variables.tf`, `outputs.tf` and
`versions.tf`. Both are instantiated from the root, so `make infra-validate`
covers them.

## Resources

- `google_project_service` for `compute`, `sqladmin` and `servicenetworking`,
  with `disable_on_destroy = false`.
- `module.vpc`: a custom-mode network (no auto subnets), one subnet using
  `subnet_cidr` with private Google access, a global address range
  (`VPC_PEERING`) and the service networking connection. The VPC module owns
  the private service access range and peering. Its outputs include
  `network_id`, `network_self_link`, `subnet_id` and `peering_range_name`.
- `module.cloudsql`: a Postgres 15 instance with private IP only (no public
  IPv4), deletion protection and backups with point-in-time recovery. It
  also creates the database and user. Outputs are the connection name,
  private IP and database name.
- `google_storage_bucket.main`: named by the `bucket_name` variable and placed
  in `region`. It enforces uniform bucket-level access and public access
  prevention, enables versioning, and does not set `force_destroy`. A
  lifecycle rule deletes objects older than 90 days.

Root outputs: `bucket_name`, `cloudsql_connection_name` and
`cloudsql_private_ip`.

## Dependency ordering

The root enables the APIs first. `module.vpc` depends on the compute and
servicenetworking services. `module.cloudsql` depends on `module.vpc`, so it
waits for the peering connection, and on the sqladmin service. Modules use no
`depends_on` on their own variables.

## Configuration

Copy the example files and replace every `REPLACE_ME` placeholder:

```sh
cd infra
cp backend.hcl.example backend.hcl
cp terraform.tfvars.example terraform.tfvars
```

- `backend.hcl` sets the state `bucket` and `prefix` for the backend.
- `terraform.tfvars` sets `project_id`, `bucket_name` and the non-secret
  database and network values (`subnet_cidr`, `db_tier`, `db_name`,
  `db_user`).

`REPLACE_ME` is a placeholder only. It is not a valid project ID or bucket
name (bucket names are globally unique, lowercase, and cannot contain
underscores), so planning or applying fails until it is replaced.

The region defaults to `us-central1`. Override it when needed:

```sh
export TF_VAR_region="your-region"
```

### Database password

`db_password` is a sensitive variable with no default. Never put it in a
committed file. Supply it from the environment:

```sh
export TF_VAR_db_password="..."
```

Marking it sensitive only hides it from output. The password is still stored
in Terraform state, so protect the state bucket and restrict access to it.

Initialize with the backend configuration, since the backend block is empty:

```sh
terraform init -backend-config=backend.hcl
```

## Validation

Validate formatting and configuration without configuring remote state:

```sh
make infra-validate
```

This command checks formatting recursively (including `modules/`), initializes
Terraform with `-backend=false`, then validates the configuration. It does not
create, change, or destroy cloud resources. `init` needs network access to
download providers.

## Cost and apply-time notes

- Applying creates billable resources, chiefly the Cloud SQL instance.
- Validation does not catch apply-time errors such as an invalid tier, or a
  `subnet_cidr` that overlaps the private service access range or existing
  ranges. Check the CIDRs before applying.
- The identity running Terraform must be allowed to enable the three APIs.
- Cloud NAT and flow logs are not configured.
- Deletion protection must be turned off before the instance can be destroyed.

## Deferred decisions

Deployment workflows are intentionally deferred, as is delivering the
database URL and password to the API and worker. Do not add credentials to
Terraform files or commit Terraform state.
