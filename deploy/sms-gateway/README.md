# Self-hosted SMS gateway (free, your own number)

This lets the AegisPass Self-Service portal send SMS (OTP codes, recovery
notices) **with no per-message fee**, using a USB GSM/4G modem and a SIM
card you already have.

## Recommended stack
- **Hardware:** a USB GSM/3G/4G modem (Huawei E3372, E173, or any
  Gammu-supported dongle), ~$15–40. Insert a SIM with an SMS plan.
- **Software:** [Gammu SMSD](https://wammu.eu/smsd/) drives the modem
  via AT commands, and [sms-gammu-gateway](https://github.com/pajikos/sms-gammu-gateway)
  exposes a tiny REST API on the LAN.
- **Why self-hosted:** you keep your own real mobile number, messages
  never leave the district network, and there is no per-SMS cost.

## Bring it up (Docker, on any Linux box on the LAN)

```bash
cd deploy/sms-gateway
docker compose up -d
```

The REST API will be available at `http://<gateway-host>:8080/messages`:

```http
POST /messages
Content-Type: application/json
{ "text": "Your AegisPass code: 123456", "recipients": ["+13405551234"] }
```

## Wire it into aegispass

Set in `.env`:

```ini
SMS_PROAegisPassR=gammu
SMS_GATEWAY_URL=http://<gateway-host>:8080
SMS_API_TOKEN=            # only if you enabled auth on the gateway
```

Then send a test from the admin **Workflows** panel
(`POST /api/sms/test`) or via:

```bash
curl -k -X POST https://passwordreset.example.com/api/sms/test \
  -H 'Content-Type: application/json' \
  -d '{"to":"+13405551234","body":"AegisPass test"}'
```

## Alternative: Twilio (SaaS number)
If you prefer a cloud number instead of self-hosting, set:
```ini
SMS_PROAegisPassR=twilio
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_FROM=+1...
```
(`pip install twilio` first.) This incurs per-message cost.

## Dev / testing
Set `SMS_PROAegisPassR=mock` — sends are logged to the audit trail and return
`True` without contacting any gateway. Good for local development.

## Security notes
- The gateway should live on a trusted LAN segment; restrict its port with
  a firewall / only allow the app host.
- Enrollment recovery SMS carries OTP-style codes — keep the gateway
  reachable only from the app and the admin network.
- Add `SMS_API_TOKEN` if you enable authentication on the gateway.
