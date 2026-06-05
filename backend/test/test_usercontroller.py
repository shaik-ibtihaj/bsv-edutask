"""
PA1417 Basic System Verification – Assignment 2: Unit Testing
Unit tests for UserController.get_user_by_email

4-Step Test Design Technique
=============================

Step 1 – Action and Expected Outcomes
--------------------------------------
Action: Call UserController.get_user_by_email(email)

Expected outcomes (all distinct behaviours the method can exhibit):
  1. Return the single matching user object.
  2. Return None (no user found).
  3. Return the first user object and print a warning (multiple users found).
  4. Raise ValueError (email string is structurally invalid).
  5. Re-raise the exception thrown by the DAO.
  [R] Raise TypeError when None is passed – robustness / implementation-behaviour
      test. The current implementation has no explicit type guard, so
      re.fullmatch raises TypeError. This is NOT part of the main specification
      oracle; it is tested separately as a robustness check.

Step 2 – Identify Conditions (Equivalence Partitioning)
---------------------------------------------------------
Condition A – Email format:
  A1: Valid   – non-empty local part, exactly one @, non-empty domain,
                no whitespace anywhere.          e.g. user@example.com
  A2: Invalid string – any string that fails the regex. Structural
      sub-cases each have one representative:
        invalidemail.com  (no @)
        ""                (empty string)
        @domain.com       (empty local part)
        user@             (empty domain)
        user@@example.com (multiple @)
        user @example.com (space in local part)
        user@example .com (space in domain part)
  A3: None – not a string at all.

Condition B – DAO return value (only reachable when A = A1):
  B1: DAO returns exactly one user
  B2: DAO returns empty list
  B3: DAO returns more than one user

Condition C – DAO behaviour (only reachable when A = A1):
  C1: DAO returns normally   (covers B1, B2, B3)
  C2: DAO raises an exception

Note: B and C are unreachable for A2 and A3 because the method exits
early before calling the DAO.

Step 3 – Condition Combinations
---------------------------------
Comb. | A              | B               | C
------+----------------+-----------------+------------------
K1    | A1 (valid)     | B1 (one user)   | C1 (normal)
K2    | A1 (valid)     | B2 (empty list) | C1 (normal)
K3    | A1 (valid)     | B3 (many users) | C1 (normal)
K4    | A1 (valid)     | n/a             | C2 (exception)
K5    | A2 (invalid)   | n/a             | n/a
K6    | A3 (None)      | n/a             | n/a

Step 4 – Expected Outcomes
---------------------------
Comb. | Expected outcome
------+---------------------------------------------------------------
K1    | Return the single user; DAO called once with {'email': email}
K2    | Return None; DAO called once
K3    | Return first user; warning printed to stdout; DAO called once
K4    | DAO exception propagates unchanged to caller
K5    | ValueError("Error: invalid email address"); DAO never called
K6    | TypeError raised by re.fullmatch; DAO never called
      |   (robustness / implementation-behaviour test)

Mapping to pytest tests:
  K1  -> TC1
  K2  -> TC2
  K3  -> TC3
  K4  -> TC12
  K5  -> TC4–TC10 (parametrised over 7 invalid-email representatives)
  K6  -> TC11
"""

import pytest
from unittest.mock import MagicMock
from src.controllers.usercontroller import UserController


# ---------------------------------------------------------------------------
# Fixtures
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
    """Unit tests for UserController.get_user_by_email (TC1–TC12).

    Each test corresponds to one combination from Step 3 of the test design:
      TC1        -> K1  (valid email, one user)
      TC2        -> K2  (valid email, empty list)
      TC3        -> K3  (valid email, multiple users)
      TC4–TC10   -> K5  (invalid email strings, parametrised)
      TC11       -> K6  (None input, robustness test)
      TC12       -> K4  (valid email, DAO exception)
    """

    # ------------------------------------------------------------------
    # TC1  (K1) – A1 + B1 + C1
    # ------------------------------------------------------------------
    def test_tc1_valid_email_dao_returns_one_user(self, sut, mocked_dao):
        """K1: Valid email, DAO returns one user → that user is returned."""
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
    # TC2  (K2) – A1 + B2 + C1
    # ------------------------------------------------------------------
    def test_tc2_valid_email_dao_returns_empty_list(self, sut, mocked_dao):
        """K2: Valid email, DAO returns [] → None is returned."""
        mocked_dao.find.return_value = []

        result = sut.get_user_by_email("notfound@example.com")

        assert result is None
        mocked_dao.find.assert_called_once_with({"email": "notfound@example.com"})

    # ------------------------------------------------------------------
    # TC3  (K3) – A1 + B3 + C1
    # ------------------------------------------------------------------
    def test_tc3_valid_email_dao_returns_multiple_users(self, sut, mocked_dao, capsys):
        """K3: Valid email, DAO returns two users → first user returned + warning."""
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
    # TC4–TC10  (K5) – A2: invalid email strings (parametrised)
    # All seven inputs are structurally distinct representatives of the
    # same equivalence class (A2 – invalid string).
    # ------------------------------------------------------------------
    @pytest.mark.parametrize(
        "invalid_email",
        [
            "invalidemail.com",   # TC4 – no @ symbol
            "",                   # TC5 – empty string
            "@domain.com",        # TC6 – empty local part
            "user@",              # TC7 – empty domain part
            "user@@example.com",  # TC8 – multiple @ symbols
            "user @example.com",  # TC9 – space in local part
            "user@example .com",  # TC10 – space in domain part
        ],
    )
    def test_tc4_to_tc10_invalid_email_raises_value_error(
        self, sut, mocked_dao, invalid_email
    ):
        """K5: Invalid email string → ValueError raised; DAO never called."""
        with pytest.raises(ValueError, match="Error: invalid email address"):
            sut.get_user_by_email(invalid_email)

        mocked_dao.find.assert_not_called()

    # ------------------------------------------------------------------
    # TC11  (K6) – A3: None input (robustness / implementation-behaviour)
    # ------------------------------------------------------------------
    def test_tc11_none_input_raises_type_error(self, sut, mocked_dao):
        """K6 (robustness): None bypasses the string guard; re.fullmatch raises
        TypeError. This tests current implementation behaviour, not a
        specification requirement."""
        with pytest.raises(TypeError):
            sut.get_user_by_email(None)

        mocked_dao.find.assert_not_called()

    # ------------------------------------------------------------------
    # TC12  (K4) – A1 + C2: DAO exception propagates
    # ------------------------------------------------------------------
    def test_tc12_dao_exception_propagates(self, sut, mocked_dao):
        """K4: Valid email, DAO raises → exception propagates unchanged."""
        mocked_dao.find.side_effect = Exception("Database connection failed")

        with pytest.raises(Exception, match="Database connection failed"):
            sut.get_user_by_email("user@example.com")
