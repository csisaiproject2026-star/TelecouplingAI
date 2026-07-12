# Production deployment controls

`production` is the canonical branch for the source deployed to MSU and GCP.
Server directories are deployment targets, not Git working copies.

## Drift audit

Run from the repository root:

```bash
python telecouplingAI-project/deploy/audit_production_drift.py
```

The audit is read-only. It compares:

- tracked deployment source with both server host-source trees;
- runtime backend files in `tele-backend` and `tele-celery-render`;
- all runtime Skill files;
- the active frontend entry point and referenced hashed assets; and
- the external User Guide assets on MSU and GCP.

Use `--skip-runtime` to compare host source only.

Server aliases, roots, observed image identities, and exclusions are defined in
`production_inventory.json`.

## Files that must remain server-specific

Never copy these between environments or include them in a source archive:

- `.env`, `.env.docker`, and backend environment files;
- TLS certificates and private keys under `nginx/certs/`;
- outputs, uploads, model data, demo inputs, and User Guide assets.

Templates such as `.env.example`, `.env.docker.gcp`, and `.env.docker.msu` may
remain in Git, but they must not replace the active server configuration.

## Safe source synchronization

1. Run the drift audit and save its output.
2. Create a timestamped backup on the target server.
3. Build an archive from the `production` Git tree using an explicit tracked
   file list.
4. Extract only source/configuration files, preserving all server-specific
   exclusions above.
5. Run the drift audit again.
6. Do not recreate or restart production containers unless that deployment was
   separately requested and validated.
