"""Demo identities and per-tab bearer sessions."""
import hashlib
import hmac
import secrets
from datetime import timedelta
from .db import now
from .demo_data import display_name

ITERATIONS = 310000


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), ITERATIONS).hex()
    return f"pbkdf2_sha256${ITERATIONS}${salt}${digest}"


def verify_password(password, stored):
    try:
        algorithm, rounds, salt, digest = stored.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(rounds)).hex()
        return hmac.compare_digest(actual, digest)
    except (ValueError, TypeError):
        return False


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def login(conn, username, password):
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM opsie_accounts WHERE username=%s AND active=1", (username,))
        account = cur.fetchone()
        if not account or not verify_password(password, account["password_hash"]):
            raise ValueError("账号或密码错误")
        token = secrets.token_urlsafe(32)
        cur.execute("INSERT INTO opsie_sessions(token_hash,account_id,expires_at) VALUES(%s,%s,%s)",
                    (token_hash(token), account["account_id"], now() + timedelta(hours=24)))
    return token, public_account(account)


def public_account(account):
    return {"account_id": str(account["account_id"]), "user_id": str(account["user_id"]),
            "role": account["role"], "display_name": display_name(account['user_id'], account['display_name'])}


def identify(conn, token):
    if not token:
        return None
    with conn.cursor() as cur:
        cur.execute("SELECT a.* FROM opsie_sessions s JOIN opsie_accounts a ON a.account_id=s.account_id "
                    "WHERE s.token_hash=%s AND s.expires_at>%s AND a.active=1", (token_hash(token), now()))
        account = cur.fetchone()
    return public_account(account) if account else None
