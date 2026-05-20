"""Migration registry for test package."""

MIGRATIONS = {
    ("1.0.0", "1.1.0"): lambda rt, rd: rd,
}
