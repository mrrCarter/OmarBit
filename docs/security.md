# Security Architecture

## API Key Management

OmarBit uses **envelope encryption** for third-party AI provider API keys:

1. Each API key is encrypted with a unique **Data Encryption Key (DEK)** using
   AES-256-GCM before storage (`api_key_ciphertext` column).
2. The DEK itself is encrypted with a **Key Encryption Key (KEK)** managed by an
   external KMS (AWS KMS, HashiCorp Vault, or equivalent).
3. `api_key_key_id` stores the KMS key reference — never the raw DEK.
4. At runtime the application fetches and decrypts the DEK from KMS, then uses
   it to decrypt the API key. Decrypted keys are held only in memory and never
   written to logs or disk.

### Key Rotation

- KEK rotation is handled by the KMS provider (automatic yearly rotation
  recommended).
- DEK rotation: re-encrypt all `api_key_ciphertext` values with a new DEK
  during a maintenance window or via a background job.

## Credential Storage

- All service credentials (Postgres, Redis, MinIO) are injected via environment
  variables using `${VAR:?required}` syntax to fail fast on missing values.
- No secrets are stored in `.env.example` — it contains only empty placeholders.
- `NEXT_PUBLIC_*` variables never contain secrets.

## Supply Chain

- `.npmrc` sets `ignore-scripts=true` by default to prevent post-install script
  attacks. CI explicitly overrides with `--ignore-scripts=false` after auditing
  dependencies.
- All GitHub Actions are pinned to full commit SHAs.
- Docker images are pinned to digest hashes.
- Build artifacts include SLSA provenance attestations.
