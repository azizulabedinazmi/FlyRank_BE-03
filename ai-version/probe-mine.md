Security probes against http://127.0.0.1:8000

| Probe | Status | Detail |
|---|---|---|
| signup response fields | 201 | 3 fields: created_at, email, id |
| signup an existing email | 409 | {"error":"A user with this email already exists"} |
| signup weak password | 400 | {"error":"Password should be at least 6 characters."} |
| 401 carries WWW-Authenticate | 401 | Bearer |
| 'BEARER <token>' (caps scheme) | 200 |  |
| 'Bearer <tab>' | 401 |  |
| forged alg=none token | 401 |  |
| 7 wrong passwords in a row | 429 | [401, 401, 401, 401, 401, 429, 429] |
