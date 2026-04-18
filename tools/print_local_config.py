#!/usr/bin/env python3
"""
Utility: Print grouped local.json as a flattened view for inspection.
"""
import json
import sys
from pathlib import Path

from backend.auth.config import AuthConfig


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "local.json"
    cfg = AuthConfig.load_from_file(path)
    flat = {
        "ldap_enabled": cfg.ldap_enabled,
        "ldap_protocol": cfg.ldap_protocol,
        "ldap_host": cfg.ldap_host,
        "ldap_port": cfg.ldap_port,
        "ldap_bind_dn_template": cfg.ldap_bind_dn_template,
        "ldap_base_dn": cfg.ldap_base_dn,
        "ldap_user_filter": cfg.ldap_user_filter,
        "ldap_tls_cacertfile": cfg.ldap_tls_cacertfile,
        "ldap_tls_verify": cfg.ldap_tls_verify,
        "ldap_admin_group_enabled": cfg.ldap_admin_group_enabled,
        "ldap_glossary_group_enabled": cfg.ldap_glossary_group_enabled,
        "ldap_admin_group": cfg.ldap_admin_group,
        "ldap_glossary_group": cfg.ldap_glossary_group,
        "ldap_group_base_dn": cfg.ldap_group_base_dn,
        "default_username": cfg.default_username,
        "session_cookie_name": cfg.session_cookie_name,
        "session_max_age": cfg.session_max_age,
        "redis_host": cfg.redis_host,
        "redis_port": cfg.redis_port,
        "redis_db": cfg.redis_db,
        "max_login_attempts": cfg.max_login_attempts,
        "login_attempt_window": cfg.login_attempt_window,
        "rate_limit_window": cfg.rate_limit_window,
    }
    print(json.dumps(flat, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()


