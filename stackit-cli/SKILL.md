---
name: stackit-cli
description: Use the STACKIT CLI (stackit) to manage STACKIT cloud resources, with a focus on authenticating and connecting kubectl to a STACKIT Kubernetes Engine (SKE) cluster. Trigger when the user mentions the stackit CLI, STACKIT cloud, SKE, "stackit ske kubeconfig", or connecting/getting a kubeconfig for a STACKIT Kubernetes cluster.
license: Apache-2.0
---

# STACKIT CLI

Command-line interface for STACKIT (the sovereign cloud for Europe). Source:
<https://github.com/stackitcloud/stackit-cli>. This skill focuses on connecting
to a STACKIT Kubernetes Engine (SKE) cluster, plus the auth/config steps that
must happen first.

## Command structure

```
stackit <GROUP> <SUB-GROUP> <COMMAND> <ARGUMENT> <PARAMETER FLAGS> [OPTION FLAGS]
```

Common option flags inherited by most commands:

- `-p, --project-id <id>` — project ID (or set via `config set` / env var)
- `--region <region>` — target region for region-specific requests
- `-o, --output-format <json|yaml|pretty|none>`
- `-y, --assume-yes` — skip confirmation prompts

Get help on any command with `-h` / `--help`, e.g. `stackit ske kubeconfig create -h`.

## Connect to a Kubernetes (SKE) cluster — quick path

This is the main workflow. It assumes the cluster already exists.

```bash
# 1. Authenticate (interactive browser login for a user account)
stackit auth login

# 2. Set the default project (and region if needed) so you don't repeat flags
stackit config set --project-id <PROJECT_ID>
stackit config set --region <REGION>        # e.g. eu01 — only if required

# 3. Find your cluster name
stackit ske cluster list

# 4. Create/merge a kubeconfig into ~/.kube/config (default: admin, 1h expiry)
stackit ske kubeconfig create <CLUSTER_NAME>

# 5. Use kubectl as normal
kubectl get nodes
```

By default `ske kubeconfig create` **merges** the cluster entry into the user's
default kubeconfig (`~/.kube/config`) and sets the current context to it.

## Authentication options

### User login (interactive)

```bash
stackit auth login          # opens a browser for the STACKIT login flow
stackit auth logout
```

### Service account (automation / CI)

Recommended for scripts. The CLI auto-discovers credentials the same way the
STACKIT SDK / Terraform provider do, then:

```bash
stackit auth activate-service-account
```

Credential resolution order (key flow, recommended over token flow):

1. `--service-account-key-path <file>` flag
2. `STACKIT_SERVICE_ACCOUNT_KEY_PATH` env var (path to the SA key JSON)
3. Credentials file at `$STACKIT_CREDENTIALS_PATH` or `$HOME/.stackit/credentials.json`

Pass the key contents directly (no file on disk) via `STACKIT_SERVICE_ACCOUNT_KEY`.
If you supplied your own RSA key-pair when creating the SA key, also provide the
PEM-encoded private key via `--private-key-path`, `STACKIT_PRIVATE_KEY_PATH`, or
`STACKIT_PRIVATE_KEY`.

Token flow (less secure, long-lived): set `--service-account-token` or
`STACKIT_SERVICE_ACCOUNT_TOKEN`.

Create a service account key:

```bash
stackit service-account key create --email <SERVICE_ACCOUNT_EMAIL>
```

## Configuration

Any config option can be overridden by an env var: take the flag name, uppercase
it, replace `-` with `_`, and prefix `STACKIT_` (e.g. `--project-id` →
`STACKIT_PROJECT_ID`). Env vars take precedence over `config set`.

```bash
stackit config set --project-id <PROJECT_ID>
stackit config set --session-time-limit 8h   # re-auth interval (max 24h)
stackit config list                           # show current config
stackit config unset --project-id            # clear a value
```

Profiles let you keep multiple configurations (e.g. per project/region):

```bash
stackit config profile create <NAME>
stackit config profile set <NAME>
stackit config profile list
```

## SKE kubeconfig variants

`stackit ske kubeconfig create <CLUSTER_NAME> [flags]` — key flags:

- (default) — embeds short-lived **admin** credentials directly in the kubeconfig
- `-e, --expiration <dur>` — admin kubeconfig lifetime; `<value><unit>` where unit
  is `s|m|h|d|M` (e.g. `30d`, `2M`). Default `1h`. Max 180 days. Cannot combine
  with `--login`.
- `-l, --login` — short-lived admin kubeconfig with **no embedded credentials**;
  kubectl fetches credentials on demand via `stackit ske kubeconfig login`
  (exec plugin). Mutually exclusive with `--expiration`.
- `--idp` — non-admin kubeconfig that authenticates via the STACKIT IDP; grants
  no cluster permissions by default (RBAC must be configured for your identity).
- `--filepath <path>` — write to a custom file instead of the default kubeconfig.
  Falls back to `$KUBECONFIG` if set, otherwise `~/.kube/config`.
- `--overwrite` — overwrite the kubeconfig file instead of merging.
- `--disable-writing` — don't write a file; print it (use with `-o json`/`yaml`).

Example — credential-less, auto-refreshing admin kubeconfig (good default for
day-to-day use; no expiry to manage):

```bash
stackit ske kubeconfig create <CLUSTER_NAME> --login
kubectl get pods   # CLI is invoked automatically to get fresh credentials
```

`stackit ske kubeconfig login` is the exec credential plugin that `--login` and
`--idp` kubeconfigs call; you normally never run it by hand.

## Other useful SKE commands

```bash
stackit ske enable                         # enable SKE on the project (one-time)
stackit ske cluster list
stackit ske cluster describe <CLUSTER_NAME>
stackit ske cluster create <CLUSTER_NAME>  # see generate-payload for full config
stackit ske cluster generate-payload       # scaffold a create/update payload JSON
stackit ske cluster delete <CLUSTER_NAME>
stackit ske options kubernetes-versions    # available k8s versions, etc.
```

## Installation (reference)

```bash
# macOS (Homebrew)
brew tap stackitcloud/tap && brew install --cask stackit

# Linux (Snap)
sudo snap install stackit --classic

# Cross-platform via mise
mise u -g github:stackitcloud/stackit-cli
```

Other methods (APT, DNF/Zypper, Nix, Scoop, eget, prebuilt binaries) are in the
repo's `INSTALLATION.md`.

## Pitfalls

- A plain `stackit ske kubeconfig create <name>` admin kubeconfig defaults to a
  **1h** expiry — it will stop working after an hour. Use `--expiration 30d` for
  a longer static config, or `--login` for an auto-refreshing one.
- Admin kubeconfigs from the CLI cap out at **180 days**. For longer-lived static
  configs, download from the STACKIT Portal.
- `--login` and `--expiration` are mutually exclusive.
- An `--idp` kubeconfig has **no cluster permissions by default**; RBAC bindings
  for your identity must exist or kubectl calls will be forbidden.
- If `--project-id` / region aren't set via `config set` or env vars, commands
  fail or hit the wrong project — set them once with `config set`.
- Env vars (e.g. `STACKIT_PROJECT_ID`) override `config set`; check both when a
  command targets an unexpected project.

## Verification

```bash
stackit auth get-access-token >/dev/null && echo "authenticated"
stackit ske cluster list                 # confirms project/region + SKE access
kubectl get nodes                        # confirms kubeconfig works end-to-end
```
