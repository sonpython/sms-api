
# SMS API Service

A lightweight SMS gateway built with **FastAPI**, designed to send SMS messages via HTTP API with **MD5 signature verification**.  
The service is exposed securely to the internet using **Cloudflare Tunnel**, without opening any inbound ports.

---

## Features

- Send SMS via HTTP API
- MD5-based request signature validation
- Vietnamese phone number format validation
- File-based SMS queue compatible with `smstools`
- Production-ready deployment (systemd + Cloudflare Tunnel)
- No inbound firewall ports required

---

## API Endpoint

```

POST /send-sms
Content-Type: application/x-www-form-urlencoded

```

---

## Parameters

| Name | Required | Description |
|---|---|---|
| `sdt` | Yes | Vietnamese phone number |
| `noidungtinnhan` | Yes | SMS message content |
| `hash` | Yes | MD5 signature |

---

## Phone Number Format

Accepted formats:
- `0xxxxxxxxx`
- `+84xxxxxxxxx`

Valid prefixes: `03, 05, 07, 08, 09`

Example:
```

0901234567
+84901234567

```

---

## Signature (MD5)

### Signature string format

```

{sdt}&{noidungtinnhan}&{SECRET_KEY}

````

- Encoding: UTF-8
- Hash algorithm: MD5
- Output: lowercase hex

### Example (Python)

```python
import hashlib

sdt = "0901234567"
message = "Test SMS"
secret_key = "YOUR_SECRET_KEY"

raw = f"{sdt}&{message}&{secret_key}"
signature = hashlib.md5(raw.encode("utf-8")).hexdigest()
````

> The message content used for hashing **must exactly match** the message sent to the API.

---

## Example Request

```bash
curl -X POST https://sms.sonpython.com/send-sms \
  -d "sdt=0901234567" \
  -d "noidungtinnhan=Test SMS" \
  -d "hash=<md5_signature>"
```

---

## Successful Response

```json
{
  "status": "OK",
  "file": "sms_1734539200_0901234567.sms"
}
```

---

## Error Responses

| HTTP Code | Error                   |
| --------- | ----------------------- |
| 400       | INVALID_VN_PHONE_FORMAT |
| 403       | INVALID_HASH            |

---

## Security Notes

* The secret key is stored **outside the repository**
* Never commit `passkey.conf`
* Each request must generate a new signature
* One request sends one SMS

---

## Deployment

* FastAPI served by Uvicorn
* Managed by systemd
* Exposed via Cloudflare Tunnel
* No public ports opened

---

## License

MIT

