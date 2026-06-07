Hướng dẫn chạy
Cài Venv
Cài các thư viện trong requirements.txt
Cài playwright để cào dữ liệu (nhân chromnium)
Cài ffmpeg để chuyển audio->text
Tạo file API_GEMINI.py, trong chứa KEY:
    GEMINI_API_KEY = "Key của phú"
Tạo credentials.json chứa KEY API Google (lên Google Cloud lấy nhá)
DB chạy sqlite nhé

Chạy backend: uvicorn main:app --port 8081
Chạy Frontend 
    Tải nodejs
    mở terminal tại thư mục frontend
        npm install -> để tải thư viện trong prj
        npm run dev -> để chạy