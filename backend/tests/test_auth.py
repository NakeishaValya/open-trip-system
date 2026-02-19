
 
from fastapi.testclient import TestClient
import pytest
from backend.main import app
from backend.auth import (
    verify_password, get_password_hash, create_access_token, verify_token, UserStorage, User,
    RegisterRequest
)
from datetime import timedelta
from fastapi import HTTPException

client = TestClient(app)

def test_password_hash_and_verify():
    pw = "password123"
    hashed = get_password_hash(pw)
    assert verify_password(pw, hashed)
    assert not verify_password("wrong", hashed)

def test_create_and_verify_token():
    data = {"sub": "userx", "user_id": "idx"}
    token = create_access_token(data, expires_delta=timedelta(minutes=1))
    payload = verify_token(token)
    assert payload["sub"] == "userx"
    with pytest.raises(HTTPException):
        verify_token("invalidtoken")

def test_userstorage_crud():
    user = User(user_id="u1", username="u1", email="u1@email.com", hashed_password="pw")
    UserStorage.save(user)
    found = UserStorage.find_by_id("u1")
    assert found is not None
    assert found.user_id == "u1"
    assert found.username == "u1"
    by_name = UserStorage.get_by_username("u1")
    assert by_name is not None
    assert by_name.user_id == "u1"
    by_email = UserStorage.get_by_email("u1@email.com")
    assert by_email is not None
    assert by_email.user_id == "u1"
    all_users = UserStorage.get_all()
    assert any(u.user_id == "u1" for u in all_users)
    assert UserStorage.delete("u1") is True
    assert UserStorage.find_by_id("u1") is None
    assert UserStorage.delete("notfound") is False

def test_register_request_validation():
    req = RegisterRequest(username="a", email="a@a.com", password="abcdef", full_name=None)
    assert req.password == "abcdef"
    with pytest.raises(ValueError):
        RegisterRequest(username="a", email="a@a.com", password="abc", full_name=None)
    with pytest.raises(ValueError):
        RegisterRequest(username="a", email="a@a.com", password="a"*73, full_name=None)

def test_login_and_me_endpoints():
    client.post("/auth/register", json={
        "username": "testuserx",
        "email": "testuserx@email.com",
        "password": "password123"
    })
    resp = client.post("/auth/login", json={"username": "testuserx", "password": "password123"})
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    resp = client.post("/auth/login", json={"username": "testuserx", "password": "wrong"})
    assert resp.status_code == 401
    resp = client.get("/auth/me")
    assert resp.status_code in (401, 403)

# --- API TESTS ---
def test_register_invalid_email():
    data = {
        "username": "user1",
        "email": "notanemail",
        "password": "password123"
    }
    response = client.post("/auth/register", json=data)
    assert response.status_code == 422

def test_register_short_password():
    data = {
        "username": "user2",
        "email": "user2@email.com",
        "password": "123"
    }
    response = client.post("/auth/register", json=data)
    assert response.status_code == 422

def test_login_invalid_user():
    data = {"username": "nouser", "password": "nopass"}
    response = client.post("/auth/login", json=data)
    assert response.status_code == 401

def test_me_unauthorized():
    response = client.get("/auth/me")
    assert response.status_code in (401, 403)
