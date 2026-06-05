"""
PA1417 Basic System Verification – Assignment 3: Integration Testing
Integration tests for DAO.create()

4-Step Test Design Technique
=============================

Step 1 – Action and Expected Outcomes
--------------------------------------
Action: Call DAO.create(data) on a real DAO connected to a real MongoDB
test collection whose validator is injected via unittest.mock.patch.

Expected outcomes:
  1. Document inserted successfully; returned object contains _id.
  2. WriteError raised (missing required field).
  3. WriteError raised (wrong BSON type).
  4. Document with a valid optional field inserted successfully.

Step 2 – Identify Conditions
------------------------------
S – Schema (collection):
  S1: user  (required: firstName, lastName, email; optional: tasks)
  S2: todo  (required: description; optional: done)

F – Required fields in document:
  F1: all required fields present
  F2: one or more required fields missing

T – BSON field types:
  T1: all supplied fields have the correct BSON type
  T2: at least one field has an incorrect BSON type

O – Optional fields:
  O1: optional field absent
  O2: optional field present with a valid type

Note: getValidator patching is test infrastructure, not a condition variable.
It is always applied so that validator loading is isolated from the
integration boundary (DAO.create <-> MongoDB). It does not vary between tests.

Step 3 – Condition Combinations
---------------------------------
Comb. | S        | F              | T              | O
------+----------+----------------+----------------+------------------
C1    | S1 user  | F1 all present | T1 valid types | O1 absent
C2    | S1 user  | F2 missing     | T1 valid types | O1 absent
C3    | S1 user  | F1 all present | T2 wrong type  | O1 absent
C4    | S1 user  | F1 all present | T1 valid types | O2 present+valid
C5    | S2 todo  | F1 all present | T1 valid types | O2 present+valid
C6    | S2 todo  | F1 all present | T1 valid types | O1 absent
C7    | S2 todo  | F2 missing     | T1 valid types | O1 absent
C8    | S2 todo  | F1 all present | T2 wrong type  | O1 absent

Step 4 – Expected Outcomes
---------------------------
C1 -> Insert success; returned doc contains _id and all input fields
C2 -> WriteError raised (missing firstName)
C3 -> WriteError raised (email supplied as integer)
C4 -> Insert success; returned doc contains _id and tasks field
C5 -> Insert success; returned doc contains _id, description, done
C6 -> Insert success; done absent from document
C7 -> WriteError raised (missing description)
C8 -> WriteError raised (done supplied as string "true")

Validator patch verification (separate from main combinations):
  test_patched_get_validator_called verifies that the test infrastructure
  is correct: src.util.dao.getValidator is patched at the right location
  and is called once during DAO construction with the correct collection
  name. This is a setup-verification test, not a DAO.create() input
  combination.
"""

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
            "lastName":  {"bsonType": "string"},
            "email":     {"bsonType": "string"},
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
            "done":        {"bsonType": "bool"}
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
            # Drop collection first to force re-creation and trigger
            # the patched getValidator call during DAO construction.
            if collection_name in db.list_collection_names():
                db[collection_name].drop()

            # Patch src.util.dao.getValidator (the exact import location used
            # by dao.py) so that validator file loading is isolated from the
            # DAO–MongoDB integration boundary under test.
            with patch("src.util.dao.getValidator", return_value=validator) as mock_gv:
                dao = DAO(collection_name=collection_name)
                created_collections.append((dao, collection_name, db))
                return dao, mock_gv

        yield _make_dao

        # Teardown: drop all test collections to prevent data accumulation.
        for dao, collection_name, database in created_collections:
            if collection_name in database.list_collection_names():
                database[collection_name].drop()

        client.close()

    # ------------------------------------------------------------------
    # TC1  (C1) – S1 user, F1 all required, T1 valid types, O1 no optional
    # ------------------------------------------------------------------
    def test_create_valid_user(self, make_dao):
        """C1: All required user fields present with correct types → insert success."""
        dao, _ = make_dao("integration_user_test", USER_VALIDATOR)

        result = dao.create({
            "firstName": "John",
            "lastName":  "Doe",
            "email":     "john.doe@example.com"
        })

        assert result is not None
        assert "_id" in result
        assert result["firstName"] == "John"
        assert result["lastName"]  == "Doe"
        assert result["email"]     == "john.doe@example.com"

    # ------------------------------------------------------------------
    # TC2  (C2) – S1 user, F2 missing required field, T1 valid types, O1
    # ------------------------------------------------------------------
    def test_create_user_missing_required_field(self, make_dao):
        """C2: Missing required field (firstName) → WriteError raised."""
        dao, _ = make_dao("integration_user_test", USER_VALIDATOR)

        with pytest.raises(WriteError):
            dao.create({
                "lastName": "Doe",
                "email":    "missing.firstname@example.com"
            })

    # ------------------------------------------------------------------
    # TC3  (C3) – S1 user, F1 all present, T2 wrong type, O1
    # ------------------------------------------------------------------
    def test_create_user_wrong_field_type(self, make_dao):
        """C3: email supplied as integer instead of string → WriteError raised."""
        dao, _ = make_dao("integration_user_test", USER_VALIDATOR)

        with pytest.raises(WriteError):
            dao.create({
                "firstName": "Test",
                "lastName":  "User",
                "email":     12345          # wrong BSON type
            })

    # ------------------------------------------------------------------
    # TC4  (C4) – S1 user, F1 all present, T1 valid types, O2 optional present
    # ------------------------------------------------------------------
    def test_create_user_with_tasks_array(self, make_dao):
        """C4: All required fields + optional tasks:[] → insert success."""
        dao, _ = make_dao("integration_user_test", USER_VALIDATOR)

        result = dao.create({
            "firstName": "With",
            "lastName":  "Tasks",
            "email":     "with.tasks@example.com",
            "tasks":     []
        })

        assert result is not None
        assert "_id" in result
        assert result["tasks"] == []

    # ------------------------------------------------------------------
    # TC5  (C5) – S2 todo, F1 all present, T1 valid types, O2 optional present
    # ------------------------------------------------------------------
    def test_create_valid_todo(self, make_dao):
        """C5: All todo fields present with correct types → insert success."""
        dao, _ = make_dao("integration_todo_test", TODO_VALIDATOR)

        result = dao.create({
            "description": "Complete assignment 3",
            "done":        False
        })

        assert result is not None
        assert "_id" in result
        assert result["description"] == "Complete assignment 3"
        assert result["done"] is False

    # ------------------------------------------------------------------
    # TC6  (C6) – S2 todo, F1 required only, T1 valid types, O1 optional absent
    # ------------------------------------------------------------------
    def test_create_todo_without_done(self, make_dao):
        """C6: Required description present, optional done absent → insert success."""
        dao, _ = make_dao("integration_todo_test", TODO_VALIDATOR)

        result = dao.create({
            "description": "Todo without done field"
        })

        assert result is not None
        assert "_id" in result
        assert result["description"] == "Todo without done field"

    # ------------------------------------------------------------------
    # TC7  (C7) – S2 todo, F2 missing required, T1 valid types, O1
    # ------------------------------------------------------------------
    def test_create_todo_missing_description(self, make_dao):
        """C7: Missing required field (description) → WriteError raised."""
        dao, _ = make_dao("integration_todo_test", TODO_VALIDATOR)

        with pytest.raises(WriteError):
            dao.create({"done": True})

    # ------------------------------------------------------------------
    # TC8  (C8) – S2 todo, F1 all present, T2 wrong type, O1
    # ------------------------------------------------------------------
    def test_create_todo_wrong_done_type(self, make_dao):
        """C8: done supplied as string "true" instead of bool → WriteError raised."""
        dao, _ = make_dao("integration_todo_test", TODO_VALIDATOR)

        with pytest.raises(WriteError):
            dao.create({
                "description": "Test wrong done type",
                "done":        "true"           # wrong BSON type
            })

    # ------------------------------------------------------------------
    # Setup verification – not part of the main DAO.create() combinations.
    # Confirms that src.util.dao.getValidator is patched at the correct
    # import location and is called exactly once during DAO construction.
    # ------------------------------------------------------------------
    def test_patched_get_validator_called(self, make_dao):
        """Setup verification: patched getValidator called once with collection name."""
        _, mock_get_validator = make_dao("integration_user_test", USER_VALIDATOR)

        mock_get_validator.assert_called_once_with("integration_user_test")
