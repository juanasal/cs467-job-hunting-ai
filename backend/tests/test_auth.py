import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

TEST_EMAIL = "testuser_lifecycle@example.com"
TEST_PASSWORD = "SecurePassword123!"


def print_step_header(step_num, title):
    print(f"\n" + "=" * 60)
    print(f" STEP {step_num}: {title}")
    print("=" * 60)


def print_step_footer(status, details=""):
    print(f"-> STATUS: {'PASSED ✅' if status else 'FAILED ❌'}")
    if details:
        print(f"-> DETAILS: {details}")
    print("-" * 60)


def test_auth_full_lifecycle():
    print("\n🚀 STARTING AUTHENTICATION LIFECYCLE TESTS")

    # -------------------------------------------------------------
    # STEP 1: POST /api/auth/register
    # -------------------------------------------------------------
    print_step_header(1, "POST /api/auth/register (User Registration)")
    print(f"Payload: email={TEST_EMAIL}, password=***")
    
    response = client.post(
        "/api/auth/register",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
    )
    print(f"Response Status Code: {response.status_code}")
    print(f"Response Body: {response.json()}")

    # 201 Created or 409 Conflict (if user already exists from a prior test run)
    success = response.status_code in [201, 409]
    print_step_footer(success, f"Code was {response.status_code} (Acceptable: 201 or 409)")
    assert success


    # -------------------------------------------------------------
    # STEP 2: POST /api/auth/login
    # -------------------------------------------------------------
    print_step_header(2, "POST /api/auth/login (User Authentication)")
    print(f"Payload: email={TEST_EMAIL}, password=***")

    response = client.post(
        "/api/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
    )
    print(f"Response Status Code: {response.status_code}")
    print(f"Response Body: {response.json()}")
    print(f"Cookies Set by Server: {list(client.cookies.keys())}")

    success = response.status_code == 200 and "user" in response.json()
    print_step_footer(success, "Session cookies successfully established.")
    assert success


    # -------------------------------------------------------------
    # STEP 3: GET /api/auth/me
    # -------------------------------------------------------------
    print_step_header(3, "GET /api/auth/me (Verify Active Session)")
    print("Sending request with active session cookie...")

    response = client.get("/api/auth/me")
    print(f"Response Status Code: {response.status_code}")
    print(f"Response Body: {response.json()}")

    success = response.status_code == 200 and response.json()["user"]["email"] == TEST_EMAIL
    print_step_footer(success, "Authenticated user profile retrieved successfully.")
    assert success


    # -------------------------------------------------------------
    # STEP 4: GET /api/auth/csrf
    # -------------------------------------------------------------
    print_step_header(4, "GET /api/auth/csrf (Retrieve CSRF Token)")
    print("Fetching CSRF token cookie/payload for state-changing request...")

    response = client.get("/api/auth/csrf")
    print(f"Response Status Code: {response.status_code}")
    data = response.json()
    print(f"Response Body: {data}")
    
    csrf_token = data.get("csrf_token")
    success = response.status_code == 200 and csrf_token is not None
    print_step_footer(success, f"CSRF token acquired: {csrf_token[:10]}...")
    assert success


    # -------------------------------------------------------------
    # STEP 5: POST /api/auth/logout
    # -------------------------------------------------------------
    print_step_header(5, "POST /api/auth/logout (Revoke Session & Clear Cookies)")
    print(f"Headers sent: Origin=http://localhost:3000, X-CSRF-Token={csrf_token[:10]}...")

    response = client.post(
        "/api/auth/logout",
        headers={
            "Origin": "http://localhost:3000",
            "X-CSRF-Token": csrf_token,
        },
    )
    print(f"Response Status Code: {response.status_code}")
    print(f"Response Body: {response.json()}")
    print(f"Remaining Cookies: {list(client.cookies.keys())}")

    success = response.status_code == 200 and response.json() == {"message": "Logged out successfully."}
    print_step_footer(success, "Session revoked and cookies cleared.")
    assert success


    # -------------------------------------------------------------
    # STEP 6: GET /api/auth/me (Post-Logout Verification)
    # -------------------------------------------------------------
    print_step_header(6, "GET /api/auth/me (Post-Logout Check)")
    print("Attempting to access /me with revoked/cleared session...")

    response = client.get("/api/auth/me")
    print(f"Response Status Code: {response.status_code}")
    print(f"Response Body: {response.json()}")

    success = response.status_code == 401
    print_step_footer(success, "Successfully rejected with 401 Unauthorized.")
    assert success

    print("\n🎉 ALL AUTHENTICATION LIFECYCLE TESTS COMPLETED SUCCESSFULLY!\n")