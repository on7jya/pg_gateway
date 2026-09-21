# Kubernetes examples for ТУЗ (`cert_dn`) mode

mTLS trust belongs at ingress. The gateway identifies the technical account by
`X-Client-Cert-DN` and loads permissions from `accounts.<DN>.grants`.

## Manifests

| File | Purpose |
|------|---------|
| `accounts-configmap.yaml` | Overlay: `authz.mode=cert_dn` + accounts (no `tenant_id`) + empty `row_filters` |
| `envoyfilter-mtls.yaml` | Istio EnvoyFilter: require peer cert; **do not** strip/rewrite `X-Client-Cert-DN` |

## Client contract

1. Present a client certificate (mTLS) to the ingress.
2. Send header `X-Client-Cert-DN` with the full Subject DN (exact match after trim).
3. Do **not** send `X-Roles` / `X-Tenant-Id` (ignored if present).
4. Do **not** send `X-Gateway-Token` (`GATEWAY_TRUST_TOKEN` is not required in `cert_dn`).

Example:

```bash
curl -s "https://gateway.example/api/v1/orders" \
  --cert client.pem --key client.key --cacert ca.pem \
  -H "X-Client-Cert-DN: CN=orders-reader,OU=tuz,O=Acme,C=RU"
```

## Wiring the overlay

Mount the ConfigMap and set:

```text
CONFIG_PATH=/config/config.yaml
ACCOUNTS_CONFIG_PATH=/config/accounts.yaml
```

Local equivalent: `config/accounts.example.yaml` with `ACCOUNTS_CONFIG_PATH`.
