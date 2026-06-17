#!/usr/bin/env python3
"""
🚀 Professional Automated Load Testing & Latency Visualization Tool
Designed for the PBL6 AI Attendance System Backend.
"""

import asyncio
import time
import argparse
import sys
import os
import json
import base64
from io import BytesIO
from typing import List, Dict, Any
from datetime import datetime

# Set console encoding to UTF-8 on Windows
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Check dependencies
try:
    import httpx
except ImportError:
    print("Error: 'httpx' is not installed. Please run: pip install httpx")
    sys.exit(1)

try:
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    import matplotlib.pyplot as plt
    import numpy as np
except ImportError:
    print("Error: 'matplotlib' or 'numpy' is not installed. Please run: pip install matplotlib numpy")
    sys.exit(1)

# Constants
DEFAULT_TARGET = "https://duckkoder.io.vn/api/v1"

class RequestResult:
    def __init__(self, start_time: float, latency: float, success: bool, status_code: int, error_msg: str = ""):
        self.start_time = start_time
        self.latency = latency  # in seconds
        self.success = success
        self.status_code = status_code
        self.error_msg = error_msg

class LoadTester:
    def __init__(self, target_url: str, concurrency: int, duration: float, workload: str, extra_args: Dict[str, Any]):
        self.target_url = target_url.rstrip('/')
        self.concurrency = concurrency
        self.duration = duration
        self.workload = workload
        self.extra_args = extra_args
        self.results: List[RequestResult] = []
        self.start_timestamp = 0.0

    async def execute_request(self, client: httpx.AsyncClient) -> RequestResult:
        start_time = time.time()
        success = False
        status_code = 0
        error_msg = ""

        try:
            if self.workload == "health":
                url = f"{self.target_url}/health"
                response = await client.get(url, timeout=10.0)
                status_code = response.status_code
                if response.status_code == 200:
                    success = True
                else:
                    error_msg = f"HTTP {response.status_code}"
            
            elif self.workload == "login":
                url = f"{self.target_url}/auth/login"
                payload = {
                    "email": self.extra_args.get("email", "loadtest_dummy@example.com"),
                    "password": self.extra_args.get("password", "DummyPassword123!"),
                    "tenant_slug": self.extra_args.get("tenant_slug", "truong-a")
                }
                response = await client.post(url, json=payload, timeout=10.0)
                status_code = response.status_code
                # We expect 401 for dummy credentials, which is a successful server response!
                if response.status_code in [200, 401]:
                    success = True
                else:
                    error_msg = f"HTTP {response.status_code}: {response.text[:100]}"
            
            elif self.workload == "dashboard":
                # Authenticated request simulator
                token = self.extra_args.get("token")
                if not token:
                    # Fallback to login first to get token
                    login_url = f"{self.target_url}/auth/login"
                    payload = {
                        "email": self.extra_args.get("email"),
                        "password": self.extra_args.get("password"),
                        "tenant_slug": self.extra_args.get("tenant_slug")
                    }
                    login_res = await client.post(login_url, json=payload, timeout=10.0)
                    if login_res.status_code == 200:
                        token = login_res.json().get("access_token")
                    else:
                        raise Exception("Auth failed for dashboard workload")
                
                headers = {"Authorization": f"Bearer {token}"}
                url = f"{self.target_url}/student/dashboard"
                response = await client.get(url, headers=headers, timeout=10.0)
                status_code = response.status_code
                if response.status_code == 200:
                    success = True
                else:
                    error_msg = f"HTTP {response.status_code}"

        except Exception as e:
            error_msg = str(e)

        latency = time.time() - start_time
        return RequestResult(start_time, latency, success, status_code, error_msg)

    async def worker(self, client: httpx.AsyncClient, stop_event: asyncio.Event):
        while not stop_event.is_set():
            result = await self.execute_request(client)
            self.results.append(result)
            # Short yield to allow other tasks to run
            await asyncio.sleep(0.001)

    async def run(self):
        print(f"\n[Load Test] Starting test on: {self.target_url}")
        print(f"Users: {self.concurrency}")
        print(f"Duration: {self.duration} seconds")
        print(f"Workload: {self.workload}")

        self.start_timestamp = time.time()
        stop_event = asyncio.Event()

        # Disable SSL warning just in case
        limits = httpx.Limits(max_keepalive_connections=self.concurrency, max_connections=self.concurrency * 2)
        async with httpx.AsyncClient(limits=limits, verify=False) as client:
            workers = [asyncio.create_task(self.worker(client, stop_event)) for _ in range(self.concurrency)]

            # Progress bar simulation
            total_steps = int(self.duration)
            for step in range(total_steps):
                await asyncio.sleep(1.0)
                elapsed = step + 1
                percent = (elapsed / self.duration) * 100
                reqs_so_far = len(self.results)
                rps = reqs_so_far / elapsed if elapsed > 0 else 0
                sys.stdout.write(f"\rProgress: [{(chr(9632) * int(percent // 5)).ljust(20)}] {percent:.1f}% | Elapsed: {elapsed}s | Requests: {reqs_so_far} | RPS: {rps:.1f}")
                sys.stdout.flush()

            # Wait for remaining fractional second
            fractional_time = self.duration - total_steps
            if fractional_time > 0:
                await asyncio.sleep(fractional_time)

            stop_event.set()
            await asyncio.gather(*workers, return_exceptions=True)

        print("\n\nTest finished. Generating statistics...")

    def compute_stats(self) -> Dict[str, Any]:
        if not self.results:
            return {}

        latencies_ms = [r.latency * 1000 for r in self.results]
        successes = [r for r in self.results if r.success]
        failures = [r for r in self.results if not r.success]

        total_reqs = len(self.results)
        success_rate = (len(successes) / total_reqs) * 100 if total_reqs > 0 else 0

        # Calculate latency percentiles
        latencies_ms.sort()
        p50 = np.percentile(latencies_ms, 50)
        p90 = np.percentile(latencies_ms, 90)
        p95 = np.percentile(latencies_ms, 95)
        p99 = np.percentile(latencies_ms, 99)
        avg_latency = np.mean(latencies_ms)
        min_latency = np.min(latencies_ms)
        max_latency = np.max(latencies_ms)

        total_time = time.time() - self.start_timestamp
        actual_rps = total_reqs / self.duration

        # Error codes summary
        error_distribution = {}
        for r in failures:
            key = r.error_msg or f"HTTP {r.status_code}"
            error_distribution[key] = error_distribution.get(key, 0) + 1

        return {
            "total_requests": total_reqs,
            "success_count": len(successes),
            "failure_count": len(failures),
            "success_rate": round(success_rate, 2),
            "avg_latency_ms": round(avg_latency, 2),
            "min_latency_ms": round(min_latency, 2),
            "max_latency_ms": round(max_latency, 2),
            "p50_ms": round(p50, 2),
            "p90_ms": round(p90, 2),
            "p95_ms": round(p95, 2),
            "p99_ms": round(p99, 2),
            "throughput_rps": round(actual_rps, 2),
            "duration": round(self.duration, 2),
            "error_distribution": error_distribution
        }

    def generate_plots(self) -> Dict[str, str]:
        """Generate latency charts and return them encoded as base64 strings."""
        if not self.results:
            return {}

        plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')

        # Create directory for plot files if not exists
        os.makedirs("plots", exist_ok=True)

        # Fig 1: Latency Distribution Histogram
        fig, ax = plt.subplots(figsize=(10, 5))
        latencies_ms = [r.latency * 1000 for r in self.results]
        ax.hist(latencies_ms, bins=50, color='#3b82f6', edgecolor='white', alpha=0.85)
        ax.set_title('Biểu đồ phân phối độ trễ (Latency Distribution)', fontsize=14, fontweight='bold', pad=15)
        ax.set_xlabel('Độ trễ (ms)', fontsize=12)
        ax.set_ylabel('Số lượng yêu cầu', fontsize=12)
        ax.axvline(np.mean(latencies_ms), color='#ef4444', linestyle='dashed', linewidth=2, label=f'Trung bình: {np.mean(latencies_ms):.1f}ms')
        ax.axvline(np.percentile(latencies_ms, 95), color='#f59e0b', linestyle='dashed', linewidth=2, label=f'p95: {np.percentile(latencies_ms, 95):.1f}ms')
        ax.legend(fontsize=10)
        plt.tight_layout()
        
        # Save to file
        plt.savefig("plots/latency_distribution.png", dpi=150)
        
        buf1 = BytesIO()
        plt.savefig(buf1, format='png', dpi=150)
        plt.close()
        plot1_b64 = base64.b64encode(buf1.getvalue()).decode('utf-8')

        # Fig 2: Latency over Time
        fig, ax = plt.subplots(figsize=(10, 5))
        relative_times = [r.start_time - self.start_timestamp for r in self.results]
        latencies_ms = [r.latency * 1000 for r in self.results]
        
        # Color coding: Green for success, Red for failure
        colors = ['#10b981' if r.success else '#ef4444' for r in self.results]
        ax.scatter(relative_times, latencies_ms, c=colors, alpha=0.6, s=15, edgecolors='none')
        ax.set_title('Độ trễ của từng Request theo tiến trình thời gian', fontsize=14, fontweight='bold', pad=15)
        ax.set_xlabel('Thời gian chạy test (giây)', fontsize=12)
        ax.set_ylabel('Độ trễ (ms)', fontsize=12)
        plt.tight_layout()
        
        # Save to file
        plt.savefig("plots/latency_over_time.png", dpi=150)
        
        buf2 = BytesIO()
        plt.savefig(buf2, format='png', dpi=150)
        plt.close()
        plot2_b64 = base64.b64encode(buf2.getvalue()).decode('utf-8')

        # Fig 3: Success vs Failure Outcome
        fig, ax = plt.subplots(figsize=(6, 5))
        success_count = sum(1 for r in self.results if r.success)
        failure_count = len(self.results) - success_count
        
        labels = ['Thành công', 'Thất bại'] if failure_count > 0 else ['Thành công']
        sizes = [success_count, failure_count] if failure_count > 0 else [success_count]
        colors = ['#10b981', '#ef4444'] if failure_count > 0 else ['#10b981']
        
        ax.pie(sizes, labels=labels, autopct='%1.1f%%', colors=colors, startangle=140, 
               textprops={'fontsize': 12, 'weight': 'bold'}, wedgeprops={'edgecolor': 'white', 'linewidth': 2})
        ax.set_title('Kết quả các yêu cầu (Request Outcomes)', fontsize=14, fontweight='bold', pad=15)
        plt.tight_layout()
        
        # Save to file
        plt.savefig("plots/request_outcome.png", dpi=150)
        
        buf3 = BytesIO()
        plt.savefig(buf3, format='png', dpi=150)
        plt.close()
        plot3_b64 = base64.b64encode(buf3.getvalue()).decode('utf-8')

        print(f"📊 Saved PNG plots to directory: {os.path.abspath('plots')}")

        return {
            "distribution": plot1_b64,
            "scatter": plot2_b64,
            "outcome": plot3_b64
        }

    def generate_html_report(self, stats: Dict[str, Any], plots: Dict[str, str], filepath: str):
        html_template = """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Báo cáo tải hệ thống chuyên nghiệp (PBL6 Load Test Report)</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #f8fafc;
            color: #1e293b;
            margin: 0;
            padding: 0;
        }
        .header {
            background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%);
            color: white;
            padding: 40px 20px;
            text-align: center;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.1);
        }
        .header h1 {
            margin: 0;
            font-size: 2.2rem;
            font-weight: 800;
        }
        .header p {
            margin: 10px 0 0 0;
            font-size: 1.1rem;
            opacity: 0.9;
        }
        .container {
            max-width: 1200px;
            margin: 30px auto;
            padding: 0 20px;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }
        .card {
            background-color: white;
            border-radius: 12px;
            padding: 24px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
            text-align: center;
            border: 1px solid #e2e8f0;
            transition: transform 0.2s;
        }
        .card:hover {
            transform: translateY(-2px);
        }
        .card .title {
            font-size: 0.9rem;
            color: #64748b;
            text-transform: uppercase;
            font-weight: 600;
            letter-spacing: 0.05em;
            margin-bottom: 8px;
        }
        .card .value {
            font-size: 1.8rem;
            font-weight: 700;
            color: #0f172a;
        }
        .card .unit {
            font-size: 1rem;
            font-weight: 500;
            color: #64748b;
        }
        .section {
            background-color: white;
            border-radius: 16px;
            padding: 30px;
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.05);
            margin-bottom: 40px;
            border: 1px solid #e2e8f0;
        }
        .section-title {
            font-size: 1.4rem;
            font-weight: 700;
            color: #1e3a8a;
            margin-top: 0;
            margin-bottom: 20px;
            border-bottom: 2px solid #eff6ff;
            padding-bottom: 10px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }
        th, td {
            text-align: left;
            padding: 12px 16px;
            border-bottom: 1px solid #e2e8f0;
        }
        th {
            background-color: #f1f5f9;
            font-weight: 600;
            color: #475569;
        }
        tr:hover {
            background-color: #f8fafc;
        }
        .plot-container {
            display: flex;
            flex-direction: column;
            gap: 30px;
            align-items: center;
        }
        .plot-box {
            background-color: white;
            padding: 15px;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.03);
            border: 1px solid #f1f5f9;
            width: 100%;
            max-width: 900px;
            text-align: center;
        }
        .plot-box img {
            max-width: 100%;
            height: auto;
            border-radius: 8px;
        }
        .status-success {
            color: #10b981;
            font-weight: bold;
        }
        .status-fail {
            color: #ef4444;
            font-weight: bold;
        }
        .footer {
            text-align: center;
            padding: 30px 20px;
            color: #94a3b8;
            font-size: 0.9rem;
            border-top: 1px solid #e2e8f0;
            margin-top: 50px;
        }
    </style>
</head>
<body>

    <div class="header">
        <h1>📊 PBL6 Load Test Report</h1>
        <p>Báo cáo kiểm thử hiệu năng và độ trễ hệ thống điểm danh tự động</p>
        <p style="font-size: 0.9rem; opacity: 0.8; margin-top: 5px;">Mục tiêu test: __TARGET_URL__ | Thời gian: __TEST_TIME__</p>
    </div>

    <div class="container">
        
        <!-- Summary Cards -->
        <div class="grid">
            <div class="card">
                <div class="title">Tổng số Requests</div>
                <div class="value">__TOTAL_REQUESTS__</div>
            </div>
            <div class="card">
                <div class="title">RPS Thực tế</div>
                <div class="value" style="color: #2563eb;">__THROUGHPUT_RPS__ <span class="unit">req/s</span></div>
            </div>
            <div class="card">
                <div class="title">Tỷ lệ thành công</div>
                <div class="value __STATUS_CLASS__">__SUCCESS_RATE__%</div>
            </div>
            <div class="card">
                <div class="title">Độ trễ trung bình</div>
                <div class="value" style="color: #f59e0b;">__AVG_LATENCY_MS__ <span class="unit">ms</span></div>
            </div>
        </div>

        <!-- Detailed Statistics Table -->
        <div class="section">
            <h2 class="section-title">⏱️ Số liệu độ trễ chi tiết (Latency Stats)</h2>
            <table>
                <thead>
                    <tr>
                        <th>Chỉ số (Percentiles)</th>
                        <th>Độ trễ (Latency)</th>
                        <th>Mô tả nghĩa</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><strong>Min</strong></td>
                        <td>__MIN_LATENCY_MS__ ms</td>
                        <td>Yêu cầu phản hồi nhanh nhất</td>
                    </tr>
                    <tr>
                        <td><strong>p50 (Median)</strong></td>
                        <td>__P50_MS__ ms</td>
                        <td>50% số request phản hồi nhanh hơn mức này</td>
                    </tr>
                    <tr>
                        <td><strong>p90</strong></td>
                        <td>__P90_MS__ ms</td>
                        <td>90% số request phản hồi nhanh hơn mức này</td>
                    </tr>
                    <tr>
                        <td><strong>p95</strong></td>
                        <td>__P95_MS__ ms</td>
                        <td>95% số request phản hồi nhanh hơn mức này (Mức chuẩn Production)</td>
                    </tr>
                    <tr>
                        <td><strong>p99</strong></td>
                        <td>__P99_MS__ ms</td>
                        <td>99% số request phản hồi nhanh hơn mức này (Mức chịu tải cực đại)</td>
                    </tr>
                    <tr>
                        <td><strong>Max</strong></td>
                        <td>__MAX_LATENCY_MS__ ms</td>
                        <td>Yêu cầu phản hồi chậm nhất</td>
                    </tr>
                </tbody>
            </table>
        </div>

        <!-- Failure Summary -->
        __FAILURE_SECTION__

        <!-- Visualized Charts -->
        <div class="section">
            <h2 class="section-title">📈 Biểu đồ trực quan hóa dữ liệu (Visualization)</h2>
            <div class="plot-container">
                <div class="plot-box">
                    <img src="data:image/png;base64,__SCATTER_PLOT__" alt="Scatter Plot">
                    <p style="margin-top: 10px; color: #64748b; font-size: 0.9rem;">Dòng thời gian phản hồi: Xem xét độ ổn định và các request bị nghẽn (spike)</p>
                </div>
                
                <div class="plot-box">
                    <img src="data:image/png;base64,__DISTRIBUTION_PLOT__" alt="Distribution Plot">
                    <p style="margin-top: 10px; color: #64748b; font-size: 0.9rem;">Phân phối tần số độ trễ: Đỉnh phân phối càng nghiêng về bên trái càng tốt</p>
                </div>

                <div class="plot-box" style="max-width: 500px;">
                    <img src="data:image/png;base64,__OUTCOME_PLOT__" alt="Outcome Plot">
                </div>
            </div>
        </div>

    </div>

    <div class="footer">
        <p>© 2026 PBL6 AI Attendance System | Thiết lập tự động kiểm thử hiệu năng nâng cao</p>
    </div>

</body>
</html>
"""
        status_class = "status-success" if stats["success_rate"] >= 95 else "status-fail"
        
        # Build failure section
        failure_section = ""
        if stats["failure_count"] > 0:
            err_rows = ""
            for err, count in stats["error_distribution"].items():
                err_rows += f'<tr><td class="status-fail">{err}</td><td><strong>{count}</strong> lần</td></tr>\n'
            failure_section = f"""
            <div class="section" style="border-left: 5px solid #ef4444;">
                <h2 class="section-title" style="color: #ef4444;">❌ Chi tiết lỗi phát sinh</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Nội dung lỗi</th>
                            <th>Số lượng phát sinh</th>
                        </tr>
                    </thead>
                    <tbody>
                        {err_rows}
                    </tbody>
                </table>
            </div>
            """

        rendered_html = html_template.replace("__TARGET_URL__", str(self.target_url)) \
                                     .replace("__TEST_TIME__", datetime.now().strftime("%d/%m/%Y %H:%M:%S")) \
                                     .replace("__TOTAL_REQUESTS__", str(stats["total_requests"])) \
                                     .replace("__THROUGHPUT_RPS__", str(stats["throughput_rps"])) \
                                     .replace("__SUCCESS_RATE__", str(stats["success_rate"])) \
                                     .replace("__AVG_LATENCY_MS__", str(stats["avg_latency_ms"])) \
                                     .replace("__MIN_LATENCY_MS__", str(stats["min_latency_ms"])) \
                                     .replace("__P50_MS__", str(stats["p50_ms"])) \
                                     .replace("__P90_MS__", str(stats["p90_ms"])) \
                                     .replace("__P95_MS__", str(stats["p95_ms"])) \
                                     .replace("__P99_MS__", str(stats["p99_ms"])) \
                                     .replace("__MAX_LATENCY_MS__", str(stats["max_latency_ms"])) \
                                     .replace("__STATUS_CLASS__", status_class) \
                                     .replace("__FAILURE_SECTION__", failure_section) \
                                     .replace("__SCATTER_PLOT__", plots["scatter"]) \
                                     .replace("__DISTRIBUTION_PLOT__", plots["distribution"]) \
                                     .replace("__OUTCOME_PLOT__", plots["outcome"])

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(rendered_html)

        print(f"📄 Report written successfully to: {filepath}")

def main():
    parser = argparse.ArgumentParser(description="PBL6 Performance Load Tester & Latency Visualizer")
    parser.add_argument("-t", "--target", default=DEFAULT_TARGET, help=f"Target API base URL (default: {DEFAULT_TARGET})")
    parser.add_argument("-u", "--users", type=int, default=50, help="Number of concurrent users (default: 50)")
    parser.add_argument("-d", "--duration", type=float, default=30.0, help="Duration of load test in seconds (default: 30)")
    parser.add_argument("-w", "--workload", choices=["health", "login", "dashboard"], default="health", help="Workload profile to test")
    parser.add_argument("-o", "--output", default="load_test_report.html", help="HTML report output file name")
    
    # Auth args for authenticated endpoints
    parser.add_argument("--email", default="student@example.com", help="Email for login")
    parser.add_argument("--password", default="Password123", help="Password for login")
    parser.add_argument("--tenant", default="truong-a", help="Tenant slug for login")

    args = parser.parse_args()

    # Prep workload parameters
    extra_args = {
        "email": args.email,
        "password": args.password,
        "tenant_slug": args.tenant
    }

    tester = LoadTester(
        target_url=args.target,
        concurrency=args.users,
        duration=args.duration,
        workload=args.workload,
        extra_args=extra_args
    )

    try:
        asyncio.run(tester.run())
    except KeyboardInterrupt:
        print("\n⚠️ Test interrupted by user.")
    
    # Compute results
    stats = tester.compute_stats()
    if not stats:
        print("❌ No request data was generated. Check connection or target URL.")
        sys.exit(1)

    print("\n" + "="*40 + "\n📊 LOAD TEST RESULTS SUMMARY\n" + "="*40)
    print(f"Target:               {tester.target_url}")
    print(f"Total Requests:       {stats['total_requests']}")
    print(f"Success Rate:         {stats['success_rate']}%")
    print(f"Throughput RPS:       {stats['throughput_rps']} req/s")
    print(f"Average Latency:      {stats['avg_latency_ms']} ms")
    print(f"Median (p50):         {stats['p50_ms']} ms")
    print(f"p90 Latency:          {stats['p90_ms']} ms")
    print(f"p95 Latency:          {stats['p95_ms']} ms")
    print(f"p99 Latency:          {stats['p99_ms']} ms")
    print(f"Min / Max Latency:    {stats['min_latency_ms']} ms / {stats['max_latency_ms']} ms")
    print("="*40)

    # Generate graphs and HTML report
    print("🎨 Rendering latency charts...")
    plots = tester.generate_plots()
    tester.generate_html_report(stats, plots, args.output)

if __name__ == "__main__":
    main()
