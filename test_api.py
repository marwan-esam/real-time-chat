from fastapi.testclient import TestClient
from app.main import app
import time

# Create a virtual browser that talks directly to FastAPI app
client = TestClient(app)

def test_health_check():
  response = client.get("/")
  assert response.status_code == 200
  assert response.json() == {"status": "The foundation is secure"}


def test_user_registration_and_login():
  unique_id = str(time.time())
  test_username = f"robot_{unique_id}"
  test_password = "password1234"

  # Test Registration
  reg_response = client.post(
    "/register",
    json={"user_name": test_username, "password": test_password}
  )

  assert reg_response.status_code == 201
  assert reg_response.json()["username"] == test_username

  # Test Authentication
  login_response = client.post(
    "/token",
    data={"username": test_username, "password": test_password}
  )
  data = login_response.json()
  assert "access_token" in data
  assert data["token_type"] == "bearer"