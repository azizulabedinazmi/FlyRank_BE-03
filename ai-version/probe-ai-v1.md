Security probes against http://127.0.0.1:8002

| Probe | Status | Detail |
|---|---|---|
| signup response fields | 201 | 26 fields: action_link, app_metadata, aud, banned_until, confirmation_sent_at, confirmed_at... |
| signup an existing email | 422 | {"error":"User already registered"} |
| signup weak password | 422 | {"error":"Password should be at least 6 characters."} |
| 401 carries WWW-Authenticate | 401 | missing |
| 'BEARER <token>' (caps scheme) | 200 |  |
| 'Bearer <tab>' | 401 |  |
| forged alg=none token | 401 |  |
| 7 wrong passwords in a row | 401 | [401, 401, 401, 401, 401, 401, 401] |
