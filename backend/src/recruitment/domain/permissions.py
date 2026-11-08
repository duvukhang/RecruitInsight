"""Single server-side role policy; the database role remains authoritative."""
PERMISSIONS = {
    'read': frozenset({'ADMIN', 'ANALYST', 'VIEWER'}),
    'predict': frozenset({'ADMIN', 'ANALYST'}),
    'manage': frozenset({'ADMIN'}),
}


def permits(role, permission):
    return role in PERMISSIONS.get(permission, ())
