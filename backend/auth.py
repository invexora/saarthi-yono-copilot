import re
from dataclasses import dataclass

import jwt
from fastapi import Header, HTTPException, status

from backend.settings import Settings


CUSTOMER_ID_PATTERN = re.compile(r"^SBI-[A-Z0-9-]{3,40}$")


@dataclass(frozen=True)
class Identity:
    subject: str
    customer_id: str
    roles: frozenset[str]

    def require_any_role(self, *allowed_roles):
        if not self.roles.intersection(allowed_roles):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient_role")


def identity_dependency(settings: Settings):
    jwks_client = jwt.PyJWKClient(settings.oidc_jwks_url, cache_keys=True, lifespan=300) if settings.auth_mode == "oidc" else None

    async def authenticate(
        authorization: str | None = Header(default=None, alias="Authorization"),
        demo_customer_id: str | None = Header(default=None, alias="X-Saarthi-Demo-Customer"),
        demo_role: str = Header(default="customer", alias="X-Saarthi-Demo-Role"),
    ) -> Identity:
        if settings.auth_mode == "development":
            if not demo_customer_id or not CUSTOMER_ID_PATTERN.fullmatch(demo_customer_id):
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="valid_demo_identity_required")
            roles = frozenset(role.strip() for role in demo_role.split(",") if role.strip())
            return Identity(subject=f"demo:{demo_customer_id}", customer_id=demo_customer_id, roles=roles or frozenset({"customer"}))

        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="bearer_token_required")

        token = authorization.removeprefix("Bearer ").strip()
        try:
            signing_key = (
                jwks_client.get_signing_key_from_jwt(token).key
                if jwks_client is not None
                else settings.jwt_secret
            )
            claims = jwt.decode(
                token,
                signing_key,
                algorithms=list(settings.oidc_algorithms) if jwks_client is not None else ["HS256"],
                issuer=settings.jwt_issuer,
                audience=settings.jwt_audience,
                options={"require": ["exp", "iat", "iss", "aud", "sub", "customer_id"]},
            )
        except jwt.PyJWTError as error:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_access_token") from error

        customer_id = claims.get("customer_id", "")
        if not CUSTOMER_ID_PATTERN.fullmatch(customer_id):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_customer_identity")
        raw_roles = claims.get("roles", ["customer"])
        if isinstance(raw_roles, str):
            raw_roles = [raw_roles]
        return Identity(
            subject=claims["sub"],
            customer_id=customer_id,
            roles=frozenset(str(role) for role in raw_roles),
        )

    return authenticate
