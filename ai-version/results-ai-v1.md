Testing http://127.0.0.1:8002 as checkpoint-0fcf6b7b9f@mailinator.com

| Check | Expected | Got | Body |
|---|---|---|---|
| 1 signup new user -> 201 | 201 | 201 FAIL | `{"user": {"id": "45918726-13df-42d0-913f-91b17dc7c2fd", "app_metadata": {"provid` |
| 1 signup without password -> 400 | 400 | 400 PASS | `{"error": "Email and password are required"}` |
| 1 signup empty body -> 400 | 400 | 400 PASS | `{"error": "Email and password are required"}` |
| 1 login empty password -> 400 | 400 | 400 PASS | `{"error": "Email and password are required"}` |
| 1 login wrong password -> 401 | 401 | 401 PASS | `{"error": "Invalid login credentials"}` |
| 1 login -> 200 with access_token | 200 | 200 PASS | `{"keys": ["access_token", "expires_in", "refresh_token", "token_type"]}` |
| 2 GET /public/info -> 200 | 200 | 200 PASS | `{"message": "Welcome stranger! This info is public."}` |
| 2 profile, no header -> 401 | 401 | 401 PASS | `{"error": "Access token required"}` |
| 2 profile, header 'Bearer' -> 401 | 401 | 401 PASS | `{"error": "Access token required"}` |
| 2 profile, header 'Bearer ' (empty) -> 401 | 401 | 401 PASS | `{"error": "Access token required"}` |
| 2 profile, header raw token, no 'Bearer ' -> 401 | 401 | 401 PASS | `{"error": "Access token required"}` |
| 2 profile, header 'Basic ...' -> 401 | 401 | 401 PASS | `{"error": "Access token required"}` |
| 2 profile, header 'Bearer a b' -> 401 | 401 | 401 PASS | `{"error": "Invalid or expired token"}` |
| 3 profile, valid token -> 200 + user | 200 | 200 PASS | `{"id": "45918726-13df-42d0-913f-91b17dc7c2fd", "email": "checkpoint-0fcf6b7b9f@m` |
| 3 profile, one char changed -> 401 | 401 | 401 PASS | `{"error": "Invalid or expired token"}` |
| 3 profile, garbage token -> 401 | 401 | 401 PASS | `{"error": "Invalid or expired token"}` |
| 4 dashboard, valid token -> 200 | 200 | 200 PASS | `{"message": "Welcome to your dashboard, checkpoint-0fcf6b7b9f@mailinator.com!", ` |
| 4 dashboard, tampered token -> 401 | 401 | 401 PASS | `{"error": "Invalid or expired token"}` |
| 4 dashboard, no token -> 401 | 401 | 401 PASS | `{"error": "Access token required"}` |
| 4 logout, no token -> 401 | 401 | 401 PASS | `{"error": "Access token required"}` |
| 4 logout, valid token -> 204 | 204 | 204 PASS | `(empty)` |
| 4 same token after logout -> 401 | 401 | 401 PASS | `{"error": "Invalid or expired token"}` |

21/22 passed
