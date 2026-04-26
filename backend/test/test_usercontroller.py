import pytest
from unittest.mock import MagicMock, patch
from src.controllers.usercontroller import UserController
from src.util.dao import DAO



@pytest.fixture
def mock_dao():
    return MagicMock(spec=DAO)


@pytest.fixture
def controller(mock_dao):
    return UserController(dao=mock_dao)



def make_user(email="alice@example.com", name="Alice"):
    return {"_id": "abc123", "email": email, "name": name}



class TestGetUserByEmailValidation:

    @pytest.mark.parametrize("bad_email", [
        "",         # empty string
        None,       # None input
        "invalid",  # missing @
        "user@",    # incomplete
        "@domain"   # incomplete
    ])
    def test_invalid_email_raises_value_error(self, controller, bad_email):
        with pytest.raises((ValueError, TypeError)):
            controller.get_user_by_email(bad_email)

    def test_validation_happens_before_dao_call(self, controller, mock_dao):
        with pytest.raises((ValueError, TypeError)):
            controller.get_user_by_email("invalid")

        mock_dao.find.assert_not_called()



class TestSingleResult:

    def test_returns_user_when_single_match(self, controller, mock_dao):
        user = make_user()
        mock_dao.find.return_value = [user]

        result = controller.get_user_by_email(user["email"])

        assert result == user

    def test_dao_called_with_correct_query(self, controller, mock_dao):
        mock_dao.find.return_value = [make_user()]

        controller.get_user_by_email("alice@example.com")

        mock_dao.find.assert_called_once_with({"email": "alice@example.com"})



class TestMultipleResults:

    def test_returns_first_user(self, controller, mock_dao):
        u1 = make_user(name="A")
        u2 = make_user(name="B")

        mock_dao.find.return_value = [u1, u2]

        result = controller.get_user_by_email("multi@x")

        assert result == u1

    def test_prints_warning(self, controller, mock_dao, capsys):
        email = "multi@x"
        mock_dao.find.return_value = [make_user(), make_user()]

        controller.get_user_by_email(email)

        captured = capsys.readouterr()
        assert email in captured.out



class TestEmptyResult:

    def test_returns_none_when_no_user_found(self, controller, mock_dao):
        mock_dao.find.return_value = []

        result = controller.get_user_by_email("ghost@x")

        # Expected behavior from specification
        assert result is None



class TestDaoErrors:

    def test_reraises_exception_from_dao(self, controller, mock_dao):
        mock_dao.find.side_effect = Exception("DB failure")

        with pytest.raises(Exception, match="DB failure"):
            controller.get_user_by_email("user@test.com")


class TestUpdate:

    def test_wraps_data_with_set(self, controller):
        with patch.object(controller.__class__.__bases__[0], "update") as mock_parent:
            mock_parent.return_value = {"nModified": 1}

            result = controller.update("id1", {"name": "Bob"})

            mock_parent.assert_called_once_with(
                id="id1",
                data={"$set": {"name": "Bob"}}
            )

            assert result == {"nModified": 1}

    def test_empty_update(self, controller):
        with patch.object(controller.__class__.__bases__[0], "update") as mock_parent:
            mock_parent.return_value = {"nModified": 0}

            controller.update("id1", {})

            mock_parent.assert_called_once_with(
                id="id1",
                data={"$set": {}}
            )
