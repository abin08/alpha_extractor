import pytest
from fastapi import status


@pytest.mark.asyncio
async def test_create_recipient_success(async_client):
    """Test that we can successfully add a new email recipient."""
    payload = {"email": "investor@example.com"}

    response = await async_client.post("/api/v1/recipients/", json=payload)

    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["email"] == "investor@example.com"
    assert data["is_active"] is True
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_bad_recipient_email(async_client):
    """Test that we can successfully add a new email recipient."""
    payload = {"email": "investorexample.com"}

    response = await async_client.post("/api/v1/recipients/", json=payload)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    error_msg = response.json()["detail"][0]["msg"]
    assert "value is not a valid email address" in error_msg


@pytest.mark.asyncio
async def test_create_recipient_duplicate(async_client):
    """Test that adding a duplicate email returns a 400 Bad Request."""
    payload = {"email": "duplicate@example.com"}

    # Insert first time
    await async_client.post("/api/v1/recipients/", json=payload)

    # Insert second time
    response = await async_client.post("/api/v1/recipients/", json=payload)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "already registered" in response.json()["detail"]


@pytest.mark.asyncio
async def test_list_recipients(async_client):
    """Test that we can retrieve the list of configured recipients."""
    payload = {"email": "list_test@example.com"}
    await async_client.post("/api/v1/recipients/", json=payload)

    response = await async_client.get("/api/v1/recipients/")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) >= 1

    # Verify our inserted email is in the returned list
    emails = [r["email"] for r in data]
    assert "list_test@example.com" in emails


@pytest.mark.asyncio
async def test_delete_recipient_success(async_client):
    """Test that an admin can remove a recipient."""
    # Create the target to delete
    payload = {"email": "remove_me@example.com"}
    create_resp = await async_client.post("/api/v1/recipients/", json=payload)
    recipient_id = create_resp.json()["id"]

    # Delete it
    response = await async_client.delete(f"/api/v1/recipients/{recipient_id}")

    assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.asyncio
async def test_delete_recipient_not_found(async_client):
    """Test that trying to delete a non-existent recipient returns a 404."""
    response = await async_client.delete("/api/v1/recipients/99999")

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == "Recipient not found."
