import pytest
from unittest.mock import MagicMock
from src.controllers.usercontroller import UserController


# ---------------------------------------------------------------------------
# Fixtures (module-level so they are shared across all test classes)
# ---------------------------------------------------------------------------

@pytest.fixture
def mocked_dao():
    """Return a MagicMock that stands in for the DAO layer."""
    return MagicMock()


@pytest.fixture
def sut(mocked_dao):
    """Return a UserController whose DAO dependency is fully mocked."""
    return UserController(dao=mocked_dao)


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestGetUserByEmail:
    """Unit tests for UserController.get_user_by_email (TC1–TC12)."""

    # ------------------------------------------------------------------
    # TC1 – Valid email, DAO returns exactly one user
    # ------------------------------------------------------------------
    def test_tc1_valid_email_dao_returns_one_user(self, sut, mocked_dao):
        """TC1: A valid email whose DAO lookup yields one result → that result is returned."""
        expected_user = {
            "_id": {"$oid": "123456789012345678901234"},
            "email": "user@example.com",
            "firstName": "John",
            "lastName": "Doe",
        }
        mocked_dao.find.return_value = [expected_user]

        result = sut.get_user_by_email("user@example.com")

        assert result == expected_user
        mocked_dao.find.assert_called_once_with({"email": "user@example.com"})

    # ------------------------------------------------------------------
    # TC2 – Valid email, DAO returns empty list
    # ------------------------------------------------------------------
    def test_tc2_valid_email_dao_returns_empty_list(self, sut, mocked_dao):
        """TC2: A valid email with no matching users → None is returned."""
        mocked_dao.find.return_value = []

        result = sut.get_user_by_email("notfound@example.com")

        assert result is None
        mocked_dao.find.assert_called_once_with({"email": "notfound@example.com"})

    # ------------------------------------------------------------------
    # TC3 – Valid email, DAO returns multiple users (warning + first user)
    # ------------------------------------------------------------------
    def test_tc3_valid_email_dao_returns_multiple_users(self, sut, mocked_dao, capsys):
        """TC3: A valid email with duplicate DB entries → first user returned + warning printed."""
        user1 = {
            "_id": {"$oid": "111111111111111111111111"},
            "email": "duplicate@example.com",
            "firstName": "John",
            "lastName": "Doe",
        }
        user2 = {
            "_id": {"$oid": "222222222222222222222222"},
            "email": "duplicate@example.com",
            "firstName": "Jane",
            "lastName": "Smith",
        }
        mocked_dao.find.return_value = [user1, user2]

        result = sut.get_user_by_email("duplicate@example.com")

        assert result == user1
        captured = capsys.readouterr()
        assert (
            "Error: more than one user found with mail duplicate@example.com"
            in captured.out
        )

    # ------------------------------------------------------------------
    # TC4–TC10 – Invalid email strings (parametrized)
    # ------------------------------------------------------------------
    @pytest.mark.parametrize(
        "invalid_email",
        [
            "invalidemail.com",   # TC4 – A2: no @ symbol
            "",                   # TC5 – A3: empty string
            "@domain.com",        # TC6 – A4: empty local part
            "user@",              # TC7 – A5: empty domain part
            "user@@example.com",  # TC8 – A6: multiple @ symbols
            "user @example.com",  # TC9 – A7: space in local part
            "user@example .com",  # TC10– A8: space in domain part
        ],
    )
    def test_tc4_to_tc10_invalid_email_raises_value_error(
        self, sut, mocked_dao, invalid_email
    ):
        """TC4–TC10: Structurally invalid emails → ValueError; DAO is never called."""
        with pytest.raises(ValueError, match="Error: invalid email address"):
            sut.get_user_by_email(invalid_email)

        mocked_dao.find.assert_not_called()

    # ------------------------------------------------------------------
    # TC11 – None input raises TypeError
    # ------------------------------------------------------------------
    def test_tc11_none_input_raises_type_error(self, sut, mocked_dao):
        """TC11: None bypasses the string guard and causes re.fullmatch to raise TypeError."""
        with pytest.raises(TypeError):
            sut.get_user_by_email(None)

        mocked_dao.find.assert_not_called()

    # ------------------------------------------------------------------
    # TC12 – DAO exception propagates unchanged
    # ------------------------------------------------------------------
    def test_tc12_dao_exception_propagates(self, sut, mocked_dao):
        """TC12: When DAO.find raises, the exception must propagate to the caller."""
        mocked_dao.find.side_effect = Exception("Database connection failed")

        with pytest.raises(Exception, match="Database connection failed"):
            sut.get_user_by_email("user@example.com")
