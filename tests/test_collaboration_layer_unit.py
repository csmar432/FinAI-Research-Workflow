"""Unit tests for scripts/core/collaboration_layer.py."""

from __future__ import annotations

import time

from scripts.core.collaboration_layer import (
    CollaborationLayer,
    CollaborationResult,
    Role,
    ROLE_PERMISSIONS,
    SharedEntry,
    SubStepCheckpoint,
    User,
)


class TestRoleEnum:
    """Role enum values."""

    def test_admin(self):
        assert Role.ADMIN.value == "admin"

    def test_researcher(self):
        assert Role.RESEARCHER.value == "researcher"

    def test_contributor(self):
        assert Role.CONTRIBUTOR.value == "contributor"

    def test_viewer(self):
        assert Role.VIEWER.value == "viewer"

    def test_guest(self):
        assert Role.GUEST.value == "guest"


class TestRolePermissions:
    """ROLE_PERMISSIONS map."""

    def test_admin_has_all(self):
        perms = ROLE_PERMISSIONS[Role.ADMIN]
        assert "read" in perms
        assert "write" in perms
        assert "admin" in perms

    def test_researcher_no_admin(self):
        perms = ROLE_PERMISSIONS[Role.RESEARCHER]
        assert "read" in perms
        assert "admin" not in perms

    def test_contributor_read_write(self):
        perms = ROLE_PERMISSIONS[Role.CONTRIBUTOR]
        assert perms == {"read", "write"}

    def test_viewer_read_only(self):
        perms = ROLE_PERMISSIONS[Role.VIEWER]
        assert perms == {"read"}

    def test_guest_no_perms(self):
        perms = ROLE_PERMISSIONS[Role.GUEST]
        assert perms == set()


class TestUserDataclass:
    """User dataclass."""

    def test_required_fields(self):
        u = User(
            user_id="u1",
            name="Alice",
            role=Role.RESEARCHER,
            created_at=time.time(),
            last_active=time.time(),
        )
        assert u.user_id == "u1"
        assert u.role == Role.RESEARCHER

    def test_default_collections(self):
        u = User(
            user_id="u1", name="x", role=Role.VIEWER,
            created_at=0, last_active=0,
        )
        assert u.shared_entries == []
        assert u.metadata == {}


class TestSharedEntryDataclass:
    """SharedEntry dataclass."""

    def test_required_fields(self):
        e = SharedEntry(
            entry_id="e1", owner_id="u1", content={"x": 1},
            shared_with={"u2": Role.VIEWER},
            created_at=time.time(), updated_at=time.time(),
            version=1,
        )
        assert e.entry_id == "e1"
        assert e.version == 1

    def test_default_annotations(self):
        e = SharedEntry(
            entry_id="e1", owner_id="u1", content="x",
            shared_with={}, created_at=0, updated_at=0, version=1,
        )
        assert e.annotations == []


class TestCollaborationResult:
    """CollaborationResult dataclass."""

    def test_required_fields(self):
        r = CollaborationResult(success=True, message="ok")
        assert r.success is True
        assert r.shared_entry is None

    def test_with_entry(self):
        entry = SharedEntry(
            entry_id="e1", owner_id="u1", content="x",
            shared_with={}, created_at=0, updated_at=0, version=1,
        )
        r = CollaborationResult(success=True, message="ok", shared_entry=entry)
        assert r.shared_entry is entry


class TestCollaborationLayerInit:
    """Constructor."""

    def test_default_init(self):
        layer = CollaborationLayer()
        assert layer.ck is None

    def test_default_admin_added(self):
        layer = CollaborationLayer()
        assert layer.get_user("system_admin") is not None

    def test_user_starts_empty_except_admin(self):
        layer = CollaborationLayer()
        # After init, only the admin is present
        non_admin = [u for u in layer.list_users() if u.user_id != "system_admin"]
        assert non_admin == []


class TestCollaborationLayerAddUser:
    """add_user() and get_user()."""

    def test_add_user_returns_user(self):
        layer = CollaborationLayer()
        u = layer.add_user("alice", "Alice", Role.RESEARCHER)
        assert u.user_id == "alice"
        assert u.role == Role.RESEARCHER

    def test_get_user_returns_added(self):
        layer = CollaborationLayer()
        layer.add_user("bob", "Bob")
        assert layer.get_user("bob").name == "Bob"

    def test_get_user_unknown_returns_none(self):
        layer = CollaborationLayer()
        assert layer.get_user("unknown") is None


class TestCollaborationLayerUpdateRole:
    """update_user_role() RBAC."""

    def test_admin_can_update_role(self):
        layer = CollaborationLayer()
        layer.add_user("alice", "Alice", Role.RESEARCHER)
        ok = layer.update_user_role("system_admin", "alice", Role.CONTRIBUTOR)
        assert ok is True
        assert layer.get_user("alice").role == Role.CONTRIBUTOR

    def test_non_admin_cannot_update_role(self):
        layer = CollaborationLayer()
        layer.add_user("alice", "Alice", Role.RESEARCHER)
        layer.add_user("bob", "Bob", Role.VIEWER)
        ok = layer.update_user_role("alice", "bob", Role.ADMIN)
        assert ok is False

    def test_update_unknown_target_returns_false(self):
        layer = CollaborationLayer()
        ok = layer.update_user_role("system_admin", "unknown_user", Role.VIEWER)
        assert ok is False


class TestCollaborationLayerListUsers:
    """list_users()."""

    def test_list_all(self):
        layer = CollaborationLayer()
        layer.add_user("alice", "Alice", Role.RESEARCHER)
        layer.add_user("bob", "Bob", Role.VIEWER)
        users = layer.list_users()
        assert len(users) >= 3  # includes admin

    def test_list_with_role_filter(self):
        layer = CollaborationLayer()
        layer.add_user("alice", "Alice", Role.RESEARCHER)
        layer.add_user("bob", "Bob", Role.VIEWER)
        users = layer.list_users(role_filter=Role.RESEARCHER)
        assert all(u.role == Role.RESEARCHER for u in users)


class TestSubStepCheckpoint:
    """SubStepCheckpoint constructor and basic methods."""

    def test_init_default_interval(self):
        s = SubStepCheckpoint(interval=5)
        assert s.interval == 5

    def test_default_strategy(self):
        from scripts.core.collaboration_layer import CheckpointStrategy
        s = SubStepCheckpoint(interval=5)
        assert s.strategy == CheckpointStrategy.EVERY_N_STEPS

    def test_should_save_every_n(self):
        s = SubStepCheckpoint(interval=5)
        # step_idx=5 is multiple of 5
        save, reason = s.should_save(5, result={})
        assert save is True
        assert "every_5" in reason

    def test_should_save_off_interval(self):
        s = SubStepCheckpoint(interval=5)
        save, _ = s.should_save(3, result={})
        assert save is False
