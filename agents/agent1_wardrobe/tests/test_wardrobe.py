"""
Tests for Wardrobe Upload, Validation, CRUD, and User Isolation.
"""

import io
from PIL import Image
from app.models.user import User
from app.core.security import hash_password, create_access_token


def create_user_and_token(db, email: str, name: str) -> tuple[int, str]:
    u = User(name=name, email=email, password_hash=hash_password("pw12345"))
    db.add(u)
    db.commit()
    db.refresh(u)
    token = create_access_token({"sub": str(u.id), "email": u.email})
    return u.id, token


def test_upload_image_and_detect_attributes(client, db_session):
    user_id, token = create_user_and_token(db_session, "test@wardrobe.ai", "Tester")

    # Generate a real in-memory image
    img = Image.new("RGB", (200, 200), color=(20, 20, 30))
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format="PNG")
    img_bytes = img_byte_arr.getvalue()

    resp = client.post(
        "/api/wardrobe/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("garment.png", img_bytes, "image/png")}
    )
    assert resp.status_code == 200
    draft = resp.json()
    assert "draft_id" in draft
    assert "detected_attributes" in draft
    attrs = draft["detected_attributes"]
    assert attrs["colour"] in ["black", "navy", "grey"]
    assert attrs["confidence"] > 0.0


def test_reject_invalid_file_format(client, db_session):
    user_id, token = create_user_and_token(db_session, "test2@wardrobe.ai", "Tester2")
    resp = client.post(
        "/api/wardrobe/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("malicious.exe", b"MZ\x90\x00not an image", "application/x-msdownload")}
    )
    assert resp.status_code == 400


def test_wardrobe_crud_and_user_isolation(client, db_session):
    u1_id, t1 = create_user_and_token(db_session, "user1@fashora.ai", "User One")
    u2_id, t2 = create_user_and_token(db_session, "user2@fashora.ai", "User Two")

    # User 1 creates an item
    create_resp = client.post(
        "/api/wardrobe",
        headers={"Authorization": f"Bearer {t1}"},
        json={
            "image_path": "uploads/sample_top.png",
            "category": "top",
            "type": "blouse",
            "colour": "black",
            "pattern": "solid",
            "style": "smart_casual",
            "formality": 0.70,
            "confidence": 0.95
        }
    )
    assert create_resp.status_code == 201
    item = create_resp.json()
    item_id = item["id"]

    # User 1 lists items -> sees their created item
    list_u1 = client.get("/api/wardrobe", headers={"Authorization": f"Bearer {t1}"})
    assert any(it["id"] == item_id for it in list_u1.json())

    # User 2 lists items -> does NOT see User 1's item
    list_u2 = client.get("/api/wardrobe", headers={"Authorization": f"Bearer {t2}"})
    assert not any(it["id"] == item_id for it in list_u2.json())

    # User 2 cannot access or delete User 1's item (IDOR protection)
    forbidden_get = client.get(f"/api/wardrobe/{item_id}", headers={"Authorization": f"Bearer {t2}"})
    assert forbidden_get.status_code == 404

    forbidden_del = client.delete(f"/api/wardrobe/{item_id}", headers={"Authorization": f"Bearer {t2}"})
    assert forbidden_del.status_code == 404

    # User 1 updates item
    update_resp = client.put(
        f"/api/wardrobe/{item_id}",
        headers={"Authorization": f"Bearer {t1}"},
        json={"material": "100% silk"}
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["material"] == "100% silk"

    # User 1 deletes item
    del_resp = client.delete(f"/api/wardrobe/{item_id}", headers={"Authorization": f"Bearer {t1}"})
    assert del_resp.status_code == 204
