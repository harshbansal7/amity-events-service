import requests
import os

ALLOWED_EXTENSIONS = {
    "png",
    "jpg",
    "jpeg",
    "gif",
    "webp",
    "bmp",
    "tiff",
    "heic",
    "svg",
    "ico",
}

FAILED_FILE_URL = "https://next-images.123rf.com/index/_next/image/?url=https://assets-cdn.123rf.com/index/static/assets/top-section-bg.jpeg&w=3840&q=75"


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_image(file):
    if file and allowed_file(file.filename):
        try:
            # Prepare the file upload to Fivemerr
            files = {"file": (file.filename, file, file.mimetype)}
            headers = {"Authorization": os.getenv("FIVEMERR_API_KEY")}

            # Make the POST request to Fivemerr
            response = requests.post(
                "https://api.fivemerr.com/v1/media/images",
                files=files,
                headers=headers,
            )

            # Check if upload was successful
            if response.status_code == 200:
                data = response.json()
                return data["url"]  # Return the CDN URL
            else:
                print(f"Fivemerr upload failed: {response.text}")
                return FAILED_FILE_URL

        except Exception as e:
            print(f"Error uploading to Fivemerr: {str(e)}")
            return FAILED_FILE_URL

    return FAILED_FILE_URL
