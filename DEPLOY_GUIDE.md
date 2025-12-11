# 🚀 Hướng dẫn Deploy Backend - Tối ưu cho Production

## 📦 So sánh kích thước Docker Image

| Phương pháp | Kích thước | Thời gian build | Phù hợp cho |
|------------|-----------|----------------|-------------|
| Dockerfile gốc (GPU) | 4-5 GB | 15-20 phút | Máy có GPU mạnh |
| Dockerfile.optimized (CPU) | 1.5-2 GB | 8-12 phút | **Production khuyến nghị** |
| Microservices (tách AI) | 200-500 MB (API) | 3-5 phút | **Khuyến nghị cao** |

## 🎯 Chiến lược Deploy (Khuyến nghị)

### **Option 1: Tách Microservices (KHUYẾN NGHỊ)**

Tách backend thành 2 services:

```
┌─────────────────────────────────────────┐
│  API Service (FastAPI)                  │
│  - Authentication                       │
│  - Database CRUD                        │
│  - Business Logic                       │
│  Size: ~300MB                           │
└────────────┬────────────────────────────┘
             │ HTTP/gRPC
             ↓
┌─────────────────────────────────────────┐
│  AI Service (Inference)                 │
│  - PyTorch Model                        │
│  - Computer Vision                      │
│  - MediaPipe                            │
│  Size: ~2GB (có thể scale riêng)        │
└─────────────────────────────────────────┘
```

**Ưu điểm:**
- API service nhẹ, deploy nhanh
- AI service có thể scale độc lập
- Tiết kiệm chi phí (AI service dùng GPU instance, API dùng CPU instance rẻ hơn)

### **Option 2: Single Service với CPU-only (Đơn giản hơn)**

Sử dụng `Dockerfile.optimized` và `requirements.prod.txt`

## 🛠️ Hướng dẫn Build & Deploy

### 1. Build với CPU-only (Khuyến nghị cho Production)

```bash
# Sử dụng requirements tối ưu
cp requirements.prod.txt requirements.txt

# Build với Dockerfile tối ưu
docker build -f Dockerfile.optimized -t pbl6-backend:prod .

# Kiểm tra kích thước
docker images pbl6-backend:prod
```

### 2. Deploy lên Cloud

#### **A. Deploy lên AWS ECS/Fargate**
```bash
# Tag image
docker tag pbl6-backend:prod <aws-account-id>.dkr.ecr.<region>.amazonaws.com/pbl6-backend:latest

# Push to ECR
aws ecr get-login-password --region <region> | docker login --username AWS --password-stdin <aws-account-id>.dkr.ecr.<region>.amazonaws.com
docker push <aws-account-id>.dkr.ecr.<region>.amazonaws.com/pbl6-backend:latest
```

#### **B. Deploy lên Google Cloud Run**
```bash
# Build và push
gcloud builds submit --tag gcr.io/<project-id>/pbl6-backend

# Deploy
gcloud run deploy pbl6-backend \
  --image gcr.io/<project-id>/pbl6-backend \
  --platform managed \
  --region asia-southeast1 \
  --memory 2Gi \
  --cpu 2 \
  --max-instances 10
```

#### **C. Deploy lên Railway/Render (Dễ nhất)**
```bash
# Railway: Kết nối GitHub repo, Railway tự động build
# Render: Kết nối GitHub repo, chọn Dockerfile

# Lưu ý: Cần upgrade plan vì image > 1GB
```

#### **D. Deploy lên VPS (Digital Ocean, Linode)**
```bash
# Trên VPS
git clone <repo>
cd back-end
docker-compose up -d

# Hoặc dùng Docker registry
docker pull <your-registry>/pbl6-backend:latest
docker run -d -p 8000:8000 --name backend <your-registry>/pbl6-backend:latest
```

### 3. Tối ưu thêm với Docker Registry Cache

```bash
# Sử dụng BuildKit cache
docker buildx build \
  --cache-from type=registry,ref=<registry>/pbl6-backend:cache \
  --cache-to type=registry,ref=<registry>/pbl6-backend:cache \
  -t pbl6-backend:latest \
  --push \
  .
```

## 🎯 Khuyến nghị cuối cùng

### Cho Development:
- Dùng `Dockerfile` gốc
- Build local với GPU (nếu có)

### Cho Production:
1. **Best Practice:** Tách microservices (API riêng, AI riêng)
2. **Đơn giản:** Dùng `Dockerfile.optimized` + `requirements.prod.txt`
3. **CPU-only PyTorch** (trừ khi có GPU instance)
4. **Cloud Storage:** Lưu model weights trên S3/GCS, tải khi khởi động
5. **Auto-scaling:** Chỉ scale AI service khi cần

## 💰 Chi phí ước tính (tham khảo)

| Platform | Instance Type | Cost/tháng | Phù hợp |
|----------|--------------|------------|---------|
| AWS ECS Fargate | 2 vCPU, 4GB RAM | $60-80 | ✅ Tốt |
| Google Cloud Run | 2 CPU, 4GB RAM | $40-60 | ✅ Tốt nhất |
| Railway (Hobby) | 8GB RAM | $20 | ⚠️ Không đủ |
| Railway (Pro) | 32GB RAM | $50 | ✅ OK |
| VPS (Digital Ocean) | 4GB RAM | $24 | ✅ Rẻ nhất |

## 🔧 Troubleshooting

### Image quá lớn (>3GB)
- ✅ Dùng `torch+cpu` thay vì torch GPU
- ✅ Chỉ cài 1 trong 2: opencv-python HOẶC opencv-contrib-python
- ✅ Loại bỏ `jax`, `jaxlib`, `polars` nếu không dùng

### Build chậm
- ✅ Sử dụng `.dockerignore`
- ✅ Multi-stage build
- ✅ Layer caching

### Out of memory khi deploy
- ✅ Tăng memory limit (ít nhất 2GB)
- ✅ Sử dụng swap (cho VPS)
- ✅ Tách AI service ra riêng

