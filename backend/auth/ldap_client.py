# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

import ssl
from typing import Optional, Dict, Any
from ldap3 import Server, Connection, ALL, SUBTREE, Tls
from ldap3.core.exceptions import LDAPException, LDAPBindError, LDAPInvalidCredentialsResult

from logger.logger import LogModule
from backend.logger import unified_logger as logger

from .config import AuthConfig
from .models import User, UserRole


def _mask_username(name: str) -> str:
    """Username masking: keep first and last characters, use × in the middle"""
    try:
        if not name:
            return ""
        if len(name) <= 2:
            return name[0] + ("×" if len(name) == 2 else "")
        return name[0] + ("×" * (len(name) - 2)) + name[-1]
    except Exception:
        return "***"


class InvalidCredentials(Exception):
    """Invalid credentials exception"""
    pass


class LDAPClient:
    """LDAP client - using ldap3 library"""
    
    def __init__(self, config: AuthConfig):
        self.config = config
        self._connection: Optional[Connection] = None
    
    def _get_connection(self) -> Connection:
        """Get LDAP connection"""
        if self._connection is None:
            ldap_uri = self.config.get_ldap_uri()
            logger.info(LogModule.AUTH, f"Initializing LDAP connection to: {ldap_uri}")
            logger.info(LogModule.AUTH, f"LDAP protocol: {self.config.ldap_protocol}")
            logger.info(LogModule.AUTH, f"LDAP host: {self.config.ldap_host}:{self.config.ldap_port}")
            
            try:
                # Create LDAP server object
                server = Server(
                    host=self.config.ldap_host,
                    port=self.config.ldap_port,
                    use_ssl=(self.config.ldap_protocol == "ldaps"),
                    get_info=ALL
                )
                logger.info(LogModule.AUTH, f"LDAP server object created successfully")
                
                # Create connection object
                self._connection = Connection(
                    server,
                    auto_bind=False,
                    receive_timeout=10,
                    auto_referrals=False
                )
                logger.info(LogModule.AUTH, "LDAP connection object created successfully")
                
                # Configure TLS options
                if self.config.ldap_protocol == "ldaps":
                    logger.info(LogModule.AUTH, "Using LDAPS protocol, configuring TLS options")
                    if self.config.ldap_tls_cacertfile:
                        logger.info(LogModule.AUTH, f"Setting TLS certificate file: {self.config.ldap_tls_cacertfile}")
                        tls = Tls(
                            local_private_key_file=None,
                            local_certificate_file=None,
                            ca_certs_file=self.config.ldap_tls_cacertfile,
                            validate=ssl.CERT_REQUIRED if self.config.ldap_tls_verify else ssl.CERT_NONE
                        )
                        server.tls = tls
                    else:
                        # Use default TLS configuration
                        tls = Tls(validate=ssl.CERT_REQUIRED if self.config.ldap_tls_verify else ssl.CERT_NONE)
                        server.tls = tls
                else:
                    logger.info(LogModule.AUTH, "Using LDAP protocol, no TLS configuration needed")
                
                logger.info(LogModule.AUTH, "LDAP connection initialization completed")
                
            except Exception as e:
                logger.error(LogModule.AUTH, f"LDAP connection initialization failed: {e}")
                raise
        
        return self._connection
    
    def authenticate(self, username: str, password: str) -> User:
        """Authenticate user credentials"""
        if not self.config.ldap_enabled:
            raise ValueError("LDAP is not enabled")
        
        logger.info(LogModule.AUTH, f"Starting LDAP authentication for user: {_mask_username(username)}")
        logger.info(LogModule.AUTH, f"LDAP configuration information:")
        logger.info(LogModule.AUTH, f"  - LDAP URI: {self.config.get_ldap_uri()}")
        logger.info(LogModule.AUTH, f"  - Protocol: {self.config.ldap_protocol}")
        logger.info(LogModule.AUTH, f"  - Host: {self.config.ldap_host}:{self.config.ldap_port}")
        logger.info(LogModule.AUTH, f"  - Bind DN Template: {self.config.ldap_bind_dn_template}")
        logger.info(LogModule.AUTH, f"  - Base DN: {self.config.ldap_base_dn}")
        logger.info(LogModule.AUTH, f"  - User Filter: {self.config.ldap_user_filter}")
        logger.info(LogModule.AUTH, f"  - TLS Cert File: {self.config.ldap_tls_cacertfile}")
        logger.info(LogModule.AUTH, f"  - TLS Verify: {self.config.ldap_tls_verify}")
        
        try:
            conn = self._get_connection()
            
            # Build bind DN
            bind_dn = self.config.ldap_bind_dn_template.format(username=username)
            logger.info(LogModule.AUTH, f"Built bind DN: {_mask_username(bind_dn)}")
            
            # Attempt bind (note: ldap3's bind() doesn't accept username/password, should use rebind())
            logger.info(LogModule.AUTH, "Attempting LDAP bind...")
            if not conn.rebind(user=bind_dn, password=password):
                logger.warning(LogModule.AUTH, f"LDAP bind failed: {conn.last_error}")
                raise InvalidCredentials("Invalid username or password")
            logger.info(LogModule.AUTH, "LDAP bind successful")
            
            # Search user information
            user_filter = self.config.ldap_user_filter.format(username=username)
            logger.info(LogModule.AUTH, f"User search filter: {user_filter}")
            logger.info(LogModule.AUTH, f"Search base DN: {self.config.ldap_base_dn}")
            
            # Execute search
            conn.search(
                search_base=self.config.ldap_base_dn,
                search_filter=user_filter,
                search_scope=SUBTREE,
                attributes=['sAMAccountName', 'displayName', 'mail', 'cn', 'memberOf']
            )
            
            logger.info(LogModule.AUTH, f"Search returned {len(conn.entries)} results")
            if conn.entries:
                logger.info(LogModule.AUTH, f"Found user, DN: {conn.entries[0].entry_dn}")
                try:
                    attrs_keys = list(conn.entries[0].entry_attributes_as_dict.keys())
                except Exception:
                    # Compatibility fallback
                    attrs_keys = []
                logger.info(LogModule.AUTH, f"User attributes: {attrs_keys}")
            
            if not conn.entries:
                logger.warning(LogModule.AUTH, "No matching user found")
                raise InvalidCredentials("User not found")
            
            # Parse user information
            user_entry = conn.entries[0]
            display_name = None
            email = None
            
            # Get display name
            if hasattr(user_entry, 'displayName') and user_entry.displayName:
                display_name = str(user_entry.displayName)
                logger.info(LogModule.AUTH, f"User display name: {display_name}")
            elif hasattr(user_entry, 'cn') and user_entry.cn:
                display_name = str(user_entry.cn)
                logger.info(LogModule.AUTH, f"User CN: {display_name}")
            
            # Get email
            if hasattr(user_entry, 'mail') and user_entry.mail:
                email = str(user_entry.mail)
                logger.info(LogModule.AUTH, f"User email: {email}")
            
            # Determine user role
            user_role = self._determine_user_role(conn, user_entry)
            logger.info(LogModule.AUTH, f"User role: {user_role}")
            
            user = User(
                username=username,
                display_name=display_name,
                email=email,
                is_authenticated=True,
                role=user_role
            )
            
            logger.info(LogModule.AUTH, f"LDAP authentication successful, user: {_mask_username(username)}")
            return user
            
        except LDAPInvalidCredentialsResult as e:
            logger.warning(LogModule.AUTH, "LDAP authentication failed: invalid credentials")
            raise InvalidCredentials("Invalid username or password")
        except LDAPBindError as e:
            logger.warning(LogModule.AUTH, f"LDAP bind error: {e}")
            raise InvalidCredentials("Invalid username or password")
        except LDAPException as e:
            logger.error(LogModule.AUTH, f"LDAP error: {e}")
            logger.error(LogModule.AUTH, f"LDAP error type: {type(e)}")
            logger.error(LogModule.AUTH, f"LDAP error details: {str(e)}")
            raise Exception(f"LDAP authentication error: {e}")
        except Exception as e:
            logger.error(LogModule.AUTH, f"Exception occurred during authentication: {e}")
            logger.error(LogModule.AUTH, f"Exception type: {type(e)}")
            raise Exception(f"Authentication error: {e}")
    
    def _determine_user_role(self, conn: Connection, user_entry) -> UserRole:
        """Determine user role based on LDAP groups"""
        logger.info(LogModule.AUTH, "Starting to determine user role...")
        logger.info(LogModule.AUTH, f"Admin group query enabled: {self.config.ldap_admin_group_enabled}")
        logger.info(LogModule.AUTH, f"App group (formerly glossary) query enabled: {self.config.ldap_glossary_group_enabled}")
        logger.info(LogModule.AUTH, f"Admin group: {self.config.ldap_admin_group}")
        logger.info(LogModule.AUTH, f"App group (formerly glossary): {self.config.ldap_glossary_group}")
        logger.info(LogModule.AUTH, f"Group search base DN: {self.config.ldap_group_base_dn}")
        
        # If both group queries are not enabled, return regular user directly
        if not self.config.ldap_admin_group_enabled and not self.config.ldap_glossary_group_enabled:
            logger.info(LogModule.AUTH, "Group queries not enabled, user defaults to regular user")
            return UserRole.LDAP_USER
        
        # If user group (now glossary group) query is enabled, only for granting additional permissions, no longer as login prerequisite
        if self.config.ldap_glossary_group_enabled:
            logger.info(LogModule.AUTH, "User group query enabled, for determining glossary-related permissions, no longer blocks login")
            is_user_group_member = self._check_user_group_membership(conn, user_entry)
            if not is_user_group_member:
                logger.info(LogModule.AUTH, "User not in user group: continue as regular user login")
        
        # If admin group query is enabled, check if user is admin group member
        if self.config.ldap_admin_group_enabled:
            logger.info(LogModule.AUTH, "Admin group query enabled, checking admin group membership")
            is_admin_group_member = self._check_admin_group_membership(conn, user_entry)
            if is_admin_group_member:
                logger.info(LogModule.AUTH, "User is admin group member, assigning admin role")
                return UserRole.LDAP_ADMIN
        
        # If user group (glossary group) is enabled and user is member, grant glossary management permission role
        if self.config.ldap_glossary_group_enabled:
            is_user_group_member = self._check_user_group_membership(conn, user_entry)
            if is_user_group_member:
                logger.info(LogModule.AUTH, "User belongs to app group, assigning ldap_app role")
                return UserRole.LDAP_APP

        # Default regular user
        logger.info(LogModule.AUTH, "User assigned as regular user role")
        return UserRole.LDAP_USER
    
    def _check_admin_group_membership(self, conn: Connection, user_entry) -> bool:
        """Check if user is admin group member"""
        try:
            # First check user's memberOf attribute
            if hasattr(user_entry, 'memberOf') and user_entry.memberOf:
                member_of_groups = [str(group) for group in user_entry.memberOf]
                logger.info(LogModule.AUTH, f"User direct member groups: {member_of_groups}")
                
                # Check if in admin group
                for group_dn in member_of_groups:
                    if self.config.ldap_admin_group.lower() in group_dn.lower():
                        logger.info(LogModule.AUTH, f"User is admin group member: {group_dn}")
                        return True
            
            # If memberOf attribute doesn't exist or no related groups found, determine through group search
            admin_group_filter = f"(&(objectClass=group)(cn={self.config.ldap_admin_group}))"
            logger.info(LogModule.AUTH, f"Search admin group filter: {admin_group_filter}")
            logger.info(LogModule.AUTH, f"Search base DN: {self.config.ldap_group_base_dn}")
            
            try:
                conn.search(
                    search_base=self.config.ldap_group_base_dn,
                    search_filter=admin_group_filter,
                    search_scope=SUBTREE,
                    attributes=['member']
                )
            except Exception as e:
                logger.warning(LogModule.AUTH, f"Group base DN search failed, trying user base DN: {e}")
                # If error encountered, try using base DN
                try:
                    conn.search(
                        search_base=self.config.ldap_base_dn,
                        search_filter=admin_group_filter,
                        search_scope=SUBTREE,
                        attributes=['member']
                    )
                    logger.info(LogModule.AUTH, "Base DN search successful")
                except Exception as e2:
                    logger.error(LogModule.AUTH, f"Base DN search also failed: {e2}")
                    raise e
            
            if conn.entries:
                admin_group_entry = conn.entries[0]
                logger.info(LogModule.AUTH, f"Found admin group: {admin_group_entry.entry_dn}")
                
                if hasattr(admin_group_entry, 'member') and admin_group_entry.member:
                    admin_members = [str(member) for member in admin_group_entry.member]
                    logger.info(LogModule.AUTH, f"Admin group member count: {len(admin_members)}")
                    
                    # Check if user is in admin group
                    if user_entry.entry_dn in admin_members:
                        logger.info(LogModule.AUTH, "User is admin group member")
                        return True
            
            logger.info(LogModule.AUTH, "User is not admin group member")
            return False
            
        except Exception as e:
            logger.error(LogModule.AUTH, f"Error occurred during admin group query: {e}")
            logger.warning(LogModule.AUTH, "Admin group query failed, assuming user is not admin group member")
            return False
    
    def _check_user_group_membership(self, conn: Connection, user_entry) -> bool:
        """Check if user is glossary group member (compatible with old fields)"""
        try:
            # First check user's memberOf attribute
            if hasattr(user_entry, 'memberOf') and user_entry.memberOf:
                member_of_groups = [str(group) for group in user_entry.memberOf]
                logger.info(LogModule.AUTH, f"User direct member groups: {member_of_groups}")
                
                # Check if in glossary group
                for group_dn in member_of_groups:
                    if self.config.ldap_glossary_group.lower() in group_dn.lower():
                        logger.info(LogModule.AUTH, f"User is glossary group member: {group_dn}")
                        return True
            
            # If memberOf attribute doesn't exist or no related groups found, determine through group search
            user_group_filter = f"(&(objectClass=group)(cn={self.config.ldap_glossary_group}))"
            logger.info(LogModule.AUTH, f"Search glossary group filter: {user_group_filter}")
            logger.info(LogModule.AUTH, f"Search base DN: {self.config.ldap_group_base_dn}")
            
            try:
                conn.search(
                    search_base=self.config.ldap_group_base_dn,
                    search_filter=user_group_filter,
                    search_scope=SUBTREE,
                    attributes=['member']
                )
            except Exception as e:
                logger.warning(LogModule.AUTH, f"Group base DN search failed, trying user base DN: {e}")
                # If error encountered, try using base DN
                try:
                    conn.search(
                        search_base=self.config.ldap_base_dn,
                        search_filter=user_group_filter,
                        search_scope=SUBTREE,
                        attributes=['member']
                    )
                    logger.info(LogModule.AUTH, "Base DN search successful")
                except Exception as e2:
                    logger.error(LogModule.AUTH, f"Base DN search also failed: {e2}")
                    raise e
            
            if conn.entries:
                user_group_entry = conn.entries[0]
                logger.info(LogModule.AUTH, f"Found glossary group: {user_group_entry.entry_dn}")
                
                if hasattr(user_group_entry, 'member') and user_group_entry.member:
                    user_members = [str(member) for member in user_group_entry.member]
                    logger.info(LogModule.AUTH, f"Glossary group member count: {len(user_members)}")
                    
                    # Check if user is in glossary group
                    if user_entry.entry_dn in user_members:
                        logger.info(LogModule.AUTH, "User is glossary group member")
                        return True
            
            logger.info(LogModule.AUTH, "User is not glossary group member")
            return False
            
        except Exception as e:
            logger.error(LogModule.AUTH, f"Error occurred during glossary group query: {e}")
            logger.warning(LogModule.AUTH, "Glossary group query failed, assuming user is not glossary group member")
            return False
    
    def close(self):
        """Close LDAP connection"""
        if self._connection:
            try:
                self._connection.unbind()
            except:
                pass
            self._connection = None
    
    def __del__(self):
        """Destructor, ensure connection is closed"""
        self.close()