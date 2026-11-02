class LegacyRouter:
    def db_for_read(self, model, **hints):
        if model._meta.app_label == "legacy":
            return "travel"
    def db_for_write(self, model, **hints):
        if model._meta.app_label == "legacy":
            raise RuntimeError("Legacy TRAVEL writes are disabled during initial migration.")
    def allow_migrate(self, db, app_label, **hints):
        if db == "travel" or app_label == "legacy":
            return False
        return None
