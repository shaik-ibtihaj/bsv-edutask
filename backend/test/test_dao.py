import os
import pytest
import pymongo
from unittest.mock import patch
from pymongo.errors import WriteError
from src.util.dao import DAO


USER_VALIDATOR = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["firstName", "lastName", "email"],
        "properties": {
            "firstName": {"bsonType": "string"},
            "lastName": {"bsonType": "string"},
            "email": {"bsonType": "string"},
            "tasks": {
                "bsonType": "array",
                "items": {"bsonType": "objectId"}
            }
        }
    }
}

TODO_VALIDATOR = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["description"],
        "properties": {
            "description": {"bsonType": "string"},
            "done": {"bsonType": "bool"}
        }
    }
}


@pytest.mark.integration
class TestDAOCreateIntegration:

    @pytest.fixture(scope="function")
    def make_dao(self, monkeypatch):
        mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
        monkeypatch.setenv("MONGO_URL", mongo_url)

        client = pymongo.MongoClient(mongo_url)
        db = client.edutask

        created_collections = []

        def _make_dao(collection_name, validator):
            if collection_name in db.list_collection_names():
                db[collection_name].drop()

            with patch("src.util.dao.getValidator", return_value=validator) as mock_get_validator:
                dao = DAO(collection_name=collection_name)
                created_collections.append((dao, collection_name, db))
                return dao, mock_get_validator

        yield _make_dao

        for dao, collection_name, database in created_collections:
            if collection_name in database.list_collection_names():
                database[collection_name].drop()

        client.close()

    # TC1: Valid user creation
    def test_create_valid_user(self, make_dao):
        dao, _ = make_dao("integration_user_test", USER_VALIDATOR)

        result = dao.create({
            "firstName": "John",
            "lastName": "Doe",
            "email": "john.doe@example.com"
        })

        assert result is not None
        assert "_id" in result
        assert result["firstName"] == "John"
        assert result["lastName"] == "Doe"
        assert result["email"] == "john.doe@example.com"

    # TC2: Missing required user field (firstName)
    def test_create_user_missing_required_field(self, make_dao):
        dao, _ = make_dao("integration_user_test", USER_VALIDATOR)

        with pytest.raises(WriteError):
            dao.create({
                "lastName": "Doe",
                "email": "missing.firstname@example.com"
            })

    # TC3: Wrong user field type (email as integer)
    def test_create_user_wrong_field_type(self, make_dao):
        dao, _ = make_dao("integration_user_test", USER_VALIDATOR)

        with pytest.raises(WriteError):
            dao.create({
                "firstName": "Test",
                "lastName": "User",
                "email": 12345
            })

    # TC4: Valid user with optional tasks array
    def test_create_user_with_tasks_array(self, make_dao):
        dao, _ = make_dao("integration_user_test", USER_VALIDATOR)

        result = dao.create({
            "firstName": "With",
            "lastName": "Tasks",
            "email": "with.tasks@example.com",
            "tasks": []
        })

        assert result is not None
        assert "_id" in result
        assert result["tasks"] == []

    # TC5: Valid todo creation
    def test_create_valid_todo(self, make_dao):
        dao, _ = make_dao("integration_todo_test", TODO_VALIDATOR)

        result = dao.create({
            "description": "Complete assignment 3",
            "done": False
        })

        assert result is not None
        assert "_id" in result
        assert result["description"] == "Complete assignment 3"
        assert result["done"] == False

    # TC6: Todo without optional done field
    def test_create_todo_without_done(self, make_dao):
        dao, _ = make_dao("integration_todo_test", TODO_VALIDATOR)

        result = dao.create({
            "description": "Todo without done field"
        })

        assert result is not None
        assert "_id" in result
        assert result["description"] == "Todo without done field"

    # TC7: Missing required todo field (description)
    def test_create_todo_missing_description(self, make_dao):
        dao, _ = make_dao("integration_todo_test", TODO_VALIDATOR)

        with pytest.raises(WriteError):
            dao.create({
                "done": True
            })

    # TC8: Wrong todo field type (done as string)
    def test_create_todo_wrong_done_type(self, make_dao):
        dao, _ = make_dao("integration_todo_test", TODO_VALIDATOR)

        with pytest.raises(WriteError):
            dao.create({
                "description": "Test wrong done type",
                "done": "true"
            })

    # TC9: Confirm patched getValidator is called with exact collection name
    def test_patched_get_validator_called(self, make_dao):
        _, mock_get_validator = make_dao("integration_user_test", USER_VALIDATOR)

        mock_get_validator.assert_called_once_with("integration_user_test")
