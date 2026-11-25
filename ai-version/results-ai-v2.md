Testing http://127.0.0.1:8002 as checkpoint-a6d0cb0c90@mailinator.com

| Check | Expected | Got | Body |
|---|---|---|---|
| 1 signup new user -> 201 | 201 | 201 PASS | `{"id": "8eba76d9-7aaf-41f0-9d6b-610718513fcb", "email": "checkpoint-a6d0cb0c90@m` |
| 1 signup without password -> 400 | 400 | 400 PASS | `{"error": "Email and password are required"}` |
| 1 signup empty body -> 400 | 400 | 400 PASS | `{"error": "Email and password are required"}` |
| 1 login empty password -> 400 | 400 | 400 PASS | `{"error": "Email and password are required"}` |
| 1 login wrong password -> 401 | 401 | 401 PASS | `{"error": "Invalid login credentials"}` |
| 1 login -> 200 with access_token | 200 | 200 PASS | `{"keys": ["access_token", "refresh_token"]}` |
| 2 GET /public/info -> 200 | 200 | 200 PASS | `{"message": "Welcome stranger! This info is public."}` |
| 2 profile, no header -> 401 | 401 | 401 PASS | `{"error": "Access token required"}` |
| 2 profile, header 'Bearer' -> 401 | 401 | 401 PASS | `{"error": "Access token required"}` |
| 2 profile, header 'Bearer ' (empty) -> 401 | 401 | 401 PASS | `{"error": "Access token required"}` |
| 2 profile, header raw token, no 'Bearer ' -> 401 | 401 | 401 PASS | `{"error": "Access token required"}` |
| 2 profile, header 'Basic ...' -> 401 | 401 | 401 PASS | `{"error": "Access token required"}` |
| 2 profile, header 'Bearer a b' -> 401 | 401 | 401 PASS | `{"error": "Invalid or expired token"}` |
| 3 profile, valid token -> 200 + user | 200 | 200 PASS | `{"id": "8eba76d9-7aaf-41f0-9d6b-610718513fcb", "email": "checkpoint-a6d0cb0c90@m` |
| 3 profile, one char changed -> 401 | 401 | 401 PASS | `{"error": "Invalid or expired token"}` |
| 3 profile, garbage token -> 401 | 401 | 401 PASS | `{"error": "Invalid or expired token"}` |
| 4 dashboard, valid token -> 200 | 200 | 200 PASS | `{"message": "Welcome to your dashboard, checkpoint-a6d0cb0c90@mailinator.com!", ` |
| 4 dashboard, tampered token -> 401 | 401 | 401 PASS | `{"error": "Invalid or expired token"}` |
| 4 dashboard, no token -> 401 | 401 | 401 PASS | `{"error": "Access token required"}` |
| 4 logout, no token -> 401 | 401 | 401 PASS | `{"error": "Access token required"}` |
| X admin route, normal user -> 403 | 403 | 403 PASS | `{"error": "Admins only"}` |
| X admin route, no token -> 401 | 401 | 401 PASS | `{"error": "Access token required"}` |
| X refresh, no token -> 400 | 400 | 400 PASS | `{"error": "refresh_token is required"}` |
| X refresh, bogus token -> 401 | 401 | 401 PASS | `{"error": "Invalid or expired refresh token"}` |
| X refresh, real token -> 200 new access_token | 200 | 200 PASS | `{"keys": ["access_token", "refresh_token"]}` |
| X refreshed token works on profile -> 200 | 200 | 200 PASS | `{"id": "8eba76d9-7aaf-41f0-9d6b-610718513fcb", "email": "checkpoint-a6d0cb0c90@m` |
| 4 logout, valid token -> 204 | 204 | 204 PASS | `(empty)` |
| 4 same token after logout -> 401 | 401 | 401 PASS | `{"error": "Invalid or expired token"}` |
| X brute force: 5x401 then 429 (got [401, 401, 401, 401, 401, 429, 429]) | 429 | 429 PASS | `{"error": "Too many failed login attempts. Try again later."}` |

29/29 passed
