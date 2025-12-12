# 1. Chọn image Python làm nền tảng
# Sử dụng 'slim' để image có kích thước nhỏ
FROM python:3.12-slim

# 2. Đặt thư mục làm việc bên trong container
WORKDIR /app

# 2.1 Cài system deps tối thiểu (tránh lỗi OpenCV/libGL trên slim)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
  && rm -rf /var/lib/apt/lists/*

# 3. Cập nhật pip và cài đặt thư viện
# Copy file requirements trước để tận dụng cache của Docker
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 4. Copy toàn bộ code của bạn vào container
COPY . .

# 5. Mở cổng (EXPOSE)
# Thay 8000 bằng cổng mà ứng dụng của bạn chạy
EXPOSE 8000

# 6. Lệnh để chạy ứng dụng (Sửa lại đường dẫn module: app.main)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]