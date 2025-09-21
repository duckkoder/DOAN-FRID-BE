# back-end
🔹 1. Tạo môi trường ảo (rất nên làm)
python -m venv venv


Kích hoạt môi trường:

Windows (PowerShell):

venv\Scripts\activate


Linux/Mac:

source venv/bin/activate

🔹 2. Cài FastAPI + Uvicorn
pip install fastapi uvicorn[standard]

🔹 3. Tạo file main.py
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Hello FastAPI 🚀"}

🔹 4. Chạy server
uvicorn main:app --reload


main = tên file main.py

app = biến FastAPI trong file

--reload = auto reload khi sửa code


Một số lệnh hay đi kèm

Để sinh file requirements.txt từ môi trường hiện tại, bạn dùng lệnh:

pip freeze > requirements.txt


Cài đặt lại từ requirements.txt trên máy khác:

pip install -r requirements.txt