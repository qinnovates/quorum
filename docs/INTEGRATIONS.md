# Integration Templates

Connect your own models through the most secure option your setup already has. Every block here is a template: copy it to `~/.config/quorum/quorum.toml`, replace everything in `<angle brackets>`, then run `quorum-run doctor`.

**Test status:** automated tests confirm that Quorum accepts every template below, and the file loader is tested directly. Only Codex CLI sign-in and a local Ollama model have been run live. Check vendor commands against that vendor's current docs.

## Pick by setup

Use the first row that fits.

| Your setup | Best option | Template |
|---|---|---|
| Local model on this machine | No key at all | [Local models](#local-models) |
| Gemini CLI or Codex CLI | The tool's own sign-in, stored in the OS keychain | [CLI sign-in](#cli-sign-in) |
| Kubernetes, Docker or systemd | A secret the platform mounts as a file | [Mounted secrets](#mounted-secrets) |
| HashiCorp Vault | Vault Agent writing a short-lived file, or the `vault` command | [HashiCorp Vault](#hashicorp-vault) |
| AWS, Google Cloud or Azure | That cloud's secret manager, with your signed-in role | [Cloud secret managers](#cloud-secret-managers) |
| Laptop with an API key | OS keychain or your password manager | [Personal vaults](#personal-vaults) |
| A tool that only injects environment variables | `api_key_env` | [Environment variables](#environment-variables) |

## Rules for every option

1. **No key in `quorum.toml`.** Quorum refuses a literal key, and a `base_url` with a login or query string.
2. **Use one key for Quorum alone**, with the least access that works and a spending limit where the provider offers one.
3. **Prefer short-lived credentials.** A login or lease that expires limits the damage from a leak.
4. **The reference lives only in your user config.** A repo's `quorum.toml` cannot add providers or key references.
5. **Models are not given your key.** Python resolves it when calling the provider, and panelists run with no access to it. A host agent running as your user could still run the same command or read the same file if it has shell access, so keep that access limited.
6. **Never store a key in a service an agent can query.** If an agent can ask for the secret, so can a prompt injection. Vault access belongs to your user or service account.

## Local models

Prompts stay on your computer and no key exists.

```toml
[providers.local]
type = "ollama"
model = "<model-from-ollama-list>"
family = "<who-trained-it>"
rank = 1
strength = 1
```

Set `family` to the developer that trained the model. A fine-tune counts as its base model's family. Keep the model server bound to localhost.

## CLI sign-in

The CLI owns the login, so Quorum never sees a token. Use `model = "default"` so the tool picks a model your account can use.

```toml
[providers.codex]
type = "codex_cli"
model = "default"
command = ["codex", "exec", "--skip-git-repo-check", "--sandbox", "read-only", "-"]
rank = 5
strength = 5
```

### Harden Codex

Add these two lines at the top of `~/.codex/config.toml`, above any `[section]`:

```text
cli_auth_credentials_store = "keyring"
forced_login_method = "chatgpt"
```

Then run `codex logout` and `codex login`. Login tokens now go to the OS keychain instead of `~/.codex/auth.json`, and an API key cannot replace the sign-in. On a machine with no keyring, keep the file and confirm its mode is `0600`. Use `codex login --device-auth` on a remote machine.

### Gemini CLI

Run `gemini` and finish sign-in. If `doctor` notes a plaintext login file, confirm the file's mode is `0600` and check Gemini CLI's current docs for keychain storage.

## Mounted secrets

The platform places the key in a file, so it stays out of the environment, process lists and shell history. This one template works for Kubernetes, Docker, systemd credentials and Vault Agent:

```toml
[providers.byo]
type = "openai_compatible"
model = "<model-id>"
base_url = "https://<your-endpoint>/v1"
family = "<who-trained-it>"
api_key_file = "/var/run/secrets/quorum/api-key"
rank = 3
strength = 3
```

Quorum reads the file when it first needs the key. The path must be absolute. The file must be small, regular, not writable by group or others, and not readable by others. Mode `0400` or `0440` passes. Symlinks are followed, because Kubernetes mounts use them.

Do not point this at a key saved in your home folder. Use it only for a file a secrets system manages.

### Kubernetes

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: quorum
spec:
  serviceAccountName: quorum
  automountServiceAccountToken: false
  securityContext:
    runAsNonRoot: true
    runAsUser: 10001
    fsGroup: 10001
  containers:
    - name: quorum
      image: <your-image>
      volumeMounts:
        - name: quorum-key
          mountPath: /var/run/secrets/quorum
          readOnly: true
  volumes:
    - name: quorum-key
      secret:
        secretName: quorum-api-key
        defaultMode: 0440
        items:
          - key: api-key
            path: api-key
```

- Enable encryption at rest for Kubernetes Secrets, because they are only base64 by default.
- Prefer External Secrets Operator or the Secrets Store CSI Driver, so the source of truth stays in Vault or your cloud manager. Both can end in the same mounted file.
- Grant RBAC read on this one secret only to whoever must manage it. The pod reads the mount and needs no API access.
- `kubectl` is deliberately not an allowed key command. It would need broad cluster credentials on the machine and returns the secret as encoded output.

### Docker

```yaml
services:
  quorum:
    image: <your-image>
    user: "10001:10001"
    secrets:
      - source: quorum_api_key
        target: /var/run/secrets/quorum/api-key
        uid: "10001"
        gid: "10001"
        mode: 0400
secrets:
  quorum_api_key:
    external: true
```

The `uid`, `gid` and `mode` options need Swarm-style secrets. A Compose file-based secret keeps the host file's mode, so set that file to `0400`.

### systemd

```ini
[Service]
LoadCredentialEncrypted=api-key:/etc/credstore.encrypted/quorum-api-key
```

Point `api_key_file` at the path in `$CREDENTIALS_DIRECTORY`, which is usually `/run/credentials/<unit-name>.service/api-key`.

## HashiCorp Vault

Start with Vault Agent when the machine runs unattended. It handles login and renewal, and writes the key to a file:

```hcl
auto_auth {
  method "kubernetes" {
    mount_path = "auth/kubernetes"
    config = {
      role = "quorum"
    }
  }
}

template {
  destination = "/var/run/secrets/quorum/api-key"
  perms       = "0400"
  contents    = "{{ with secret \"secret/data/quorum/byo\" }}{{ .Data.data.api_key }}{{ end }}"
}
```

Use the `api_key_file` template above with that path. Keep the destination on a memory-backed volume.

For a person at a laptop, use the `vault` command after `vault login`:

```toml
[providers.byo]
type = "openai_compatible"
model = "<model-id>"
base_url = "https://<your-endpoint>/v1"
family = "<who-trained-it>"
api_key_cmd = ["vault", "kv", "get", "-field=api_key", "secret/quorum/byo"]
rank = 3
strength = 3
```

Limit the Vault policy to reading that one path:

```hcl
path "secret/data/quorum/byo" {
  capabilities = ["read"]
}
```

`VAULT_ADDR` must use HTTPS, and your Vault login stays in Vault's own token helper.

## Cloud secret managers

Each uses the role you are already signed in with, so no long-lived cloud key is needed. Keep the rest of the provider block as above and change only the key line.

AWS Secrets Manager:

```toml
[providers.byo]
type = "openai_compatible"
model = "<model-id>"
base_url = "https://<your-endpoint>/v1"
family = "<who-trained-it>"
api_key_cmd = ["aws", "secretsmanager", "get-secret-value", "--secret-id", "quorum/byo", "--query", "SecretString", "--output", "text"]
rank = 3
strength = 3
```

Google Cloud Secret Manager:

```toml
[providers.byo]
type = "openai_compatible"
model = "<model-id>"
base_url = "https://<your-endpoint>/v1"
family = "<who-trained-it>"
api_key_cmd = ["gcloud", "secrets", "versions", "access", "latest", "--secret=quorum-byo"]
rank = 3
strength = 3
```

Azure Key Vault:

```toml
[providers.byo]
type = "openai_compatible"
model = "<model-id>"
base_url = "https://<your-endpoint>/v1"
family = "<who-trained-it>"
api_key_cmd = ["az", "keyvault", "secret", "show", "--vault-name", "<your-vault>", "--name", "quorum-byo", "--query", "value", "--output", "tsv"]
rank = 3
strength = 3
```

Inside a cluster, prefer workload identity (IRSA, GKE Workload Identity or Azure Workload Identity) with the mounted-file pattern.

## Personal vaults

macOS Keychain:

```toml
[providers.byo]
type = "openai_compatible"
model = "<model-id>"
base_url = "https://<your-endpoint>/v1"
family = "<who-trained-it>"
api_key_cmd = ["security", "find-generic-password", "-s", "quorum/byo", "-w"]
rank = 3
strength = 3
```

Change only the `api_key_cmd` line for the others:

| Store | `api_key_cmd` |
|---|---|
| Linux Secret Service | `["secret-tool", "lookup", "service", "quorum-byo"]` |
| `pass` | `["pass", "show", "quorum/byo"]` |
| 1Password | `["op", "read", "op://<vault>/quorum-byo/credential"]` |
| Bitwarden | `["bw", "get", "password", "quorum-byo"]` |
| Doppler | `["doppler", "secrets", "get", "QUORUM_BYO_KEY", "--plain"]` |
| SOPS | `["sops", "--decrypt", "--extract", "[\"api_key\"]", "<path-to-encrypted-file>"]` |

Enter the key through the vault's own prompt. Do not type it into a command, because shell history records it.

## Environment variables

Use this only when a tool injects the variable for you, such as `op run`, `doppler run` or `vault agent` in process-supervisor mode. Exporting a key in a shell profile is the same as saving it in a file.

```toml
[providers.byo]
type = "openai_compatible"
model = "<model-id>"
base_url = "https://<your-endpoint>/v1"
family = "<who-trained-it>"
api_key_env = "QUORUM_BYO_API_KEY"
rank = 3
strength = 3
```

## Check your setup

```bash
quorum-run doctor
quorum-run doctor --live --allow-provider <name>
```

`doctor` never prints a key. `--live` sends one short test prompt, only to providers you name.

| `doctor` says | Meaning | Fix |
|---|---|---|
| `NOTE ... kept in a plaintext file` | A CLI login sits in a file | Move it to the keychain as above |
| `FIX ... open to other users` | A login file has loose permissions | `chmod 600` it, then sign in again |
| `This model is not available` | The login works, but a pinned model is stale or not on your plan | Use `model = "default"`, and remove any pin in the tool's own config |
| `Sign in again` | The login expired or was revoked | Sign in through the tool. Run `<tool> logout` first if a token cannot refresh |
| `api_key_file ... is open to other users` | The mounted file's mode is too open | Set it to `0400` or `0440` |
| `api_key_cmd ... returned no value` | The vault is locked, or the path is wrong | Run the command yourself, without printing it to a shared screen |

A login check is not enough. A tool can report that you are signed in while a real call fails, so always finish with `--live`.
