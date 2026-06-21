import mimetypes
from pathlib import Path
import asyncio

from dotenv import load_dotenv
from minio.error import S3Error


APP_DIR = Path(__file__).resolve().parents[1]
load_dotenv(APP_DIR / ".env")


from core.database import db, client
from core.minio import minio_client, MINIO_BUCKET


BASE_DIR = APP_DIR
AVATAR_DIR = BASE_DIR / "assets" / "account_avatars"


ACCOUNT_AVATARS = {
    "hcmute@utezone.com": "hcmute.png",
    "fit.hcmute@utezone.com": "fit.png",
    "feet.hcmute@utezone.com": "feet.jpg",
    "feee.hcmute@utezone.com": "feee.png",
    "fme.hcmute@utezone.com": "fme.jpg",
    "fas.hcmute@utezone.com": "fas.jpg",
    "fce.hcmute@utezone.com": "fce.jpg",
    "fe.hcmute@utezone.com": "fe.png",
    "ffl.hcmute@utezone.com": "ffl.png",
    "fcft.hcmute@utezone.com": "fcft.png",
    "fgam.hcmute@utezone.com": "fgam.jpg",
    "fgtfd.hcmute@utezone.com": "fgtfd.jpg",
    "fpi.hcmute@utezone.com": "fpi.png",
    "fae.hcmute@utezone.com": "fae.jpeg",
    "ite.hcmute@utezone.com": "ite.jpg",
}


def make_stable_file_id(email: str, filename: str) -> str:
    """
    Tạo file_id cố định để chạy lại script không sinh file rác.
    Ví dụ:
    fit.hcmute@utezone.com + fit.png
    -> account_avatar_fit_hcmute_utezone_com.png
    """
    ext = Path(filename).suffix.lower()

    safe_email = (
        email.replace("@", "_")
        .replace(".", "_")
        .replace("-", "_")
    )

    return f"account_avatar_{safe_email}{ext}"


def ensure_bucket_exists():
    try:
        if not minio_client.bucket_exists(MINIO_BUCKET):
            minio_client.make_bucket(MINIO_BUCKET)
    except S3Error as e:
        raise RuntimeError(f"Lỗi khi kiểm tra/tạo bucket MinIO: {e}")


def upload_avatar_to_minio(file_path: Path, object_name: str):
    content_type, _ = mimetypes.guess_type(str(file_path))

    if not content_type:
        content_type = "application/octet-stream"

    file_size = file_path.stat().st_size

    with file_path.open("rb") as file_data:
        minio_client.put_object(
            bucket_name=MINIO_BUCKET,
            object_name=object_name,
            data=file_data,
            length=file_size,
            content_type=content_type,
        )


async def seed_account_avatars():
    if not AVATAR_DIR.exists():
        raise FileNotFoundError(f"Không tìm thấy folder avatar: {AVATAR_DIR}")

    try:
        await client.admin.command("ping")
        print("Connected to MongoDB successfully.")
    except Exception as e:
        raise RuntimeError(f"Failed to connect to MongoDB: {e}")

    ensure_bucket_exists()

    account_collection = db["account"]

    success_count = 0
    skip_count = 0
    missing_file_count = 0
    missing_account_count = 0

    for email, filename in ACCOUNT_AVATARS.items():
        file_path = AVATAR_DIR / filename

        if not file_path.exists():
            print(f"[MISSING FILE] {email} -> {file_path}")
            missing_file_count += 1
            continue

        account = await account_collection.find_one({"email": email})

        if not account:
            print(f"[MISSING ACCOUNT] {email}")
            missing_account_count += 1
            continue

        file_id = make_stable_file_id(email, filename)

        upload_avatar_to_minio(file_path, file_id)

        result = await account_collection.update_one(
            {"email": email},
            {
                "$set": {
                    "userInfo.avatar": file_id
                }
            }
        )

        if result.modified_count > 0:
            print(f"[UPDATED] {email} -> {file_id}")
            success_count += 1
        else:
            print(f"[SKIPPED] {email} đã có avatar giống hiện tại -> {file_id}")
            skip_count += 1

    print("\nDone.")
    print(f"Updated: {success_count}")
    print(f"Skipped: {skip_count}")
    print(f"Missing files: {missing_file_count}")
    print(f"Missing accounts: {missing_account_count}")


if __name__ == "__main__":
    asyncio.run(seed_account_avatars())