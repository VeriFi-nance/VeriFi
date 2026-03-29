---
name: django-api-guidelines
description: Use this whenever writing or modifying Python backend code, Django views, models, or serializers in the backend/ directory.
---
# Django API Rules
- **Framework**: Use `APIView` + plain `Serializer`. No `ModelViewSet` or `ModelSerializer` unless justified by a 1-to-1 model mapping.
- **Architecture**: Keep views thin. Business logic (claim detection, scoring, nonces) lives in `accounts/services.py` or a feature app's `services.py`. Serializers validate shape only.
- **Models**: Minimal (`WalletUser(address, created_at)`). Do NOT use Django's built-in `User` model.
- **Auth**: `rest_framework_simplejwt`. Produce tokens with `RefreshToken()`, add custom claims (`refresh["address"] = ...`). No Django sessions or cookies.
- **Errors**: Return `{"detail": "..."}` with standard HTTP status codes.