from playwright.async_api import async_playwright
import asyncio
from pathlib import Path

# Dùng đường dẫn tuyệt đối an toàn cho cả khi chạy script qua systemd/cronjob
STATE_FILE = Path(__file__).parent / "hust_state.json"
TARGET_URL = "https://ctt-sis.hust.edu.vn/Students/Timetables.aspx"

async def renew_session():
    print("\nKhởi tạo luồng cấp lại Session...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        print("[HỆ THỐNG] Đang mở SIS. Huynh vui lòng đăng nhập qua Microsoft SSO...")
        await page.goto(TARGET_URL)

        try:
            # Chờ vô cực cho đến khi request được redirect thành công về đúng route lịch học
            await page.wait_for_url("**/Students/Timetables.aspx*", timeout=0)
            
            # Đảm bảo DOM đã mount xong module DevExpress
            await page.wait_for_selector('tr[class*="dxgvDataRow_"]', timeout=30000)
            
            # Flush storage state ra đĩa
            await context.storage_state(path=STATE_FILE)
            print(f"[HỆ THỐNG] State persistence thành công: {STATE_FILE}")
            
        except Exception as e:
            print(f"[LỖI] Interrupt luồng đăng nhập: {e}")
            
        finally:
            await browser.close()


async def crawl_timetable():
    """Hàm worker chạy ngầm hút data"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        # Inject state từ file JSON
        context = await browser.new_context(storage_state=STATE_FILE)
        page = await context.new_page()

        print("[WORKER] Đang nạp trang thời khóa biểu...")
        await page.goto(TARGET_URL, wait_until="networkidle")

        try:
            print("[WORKER] Đang đợi thẻ Grid View DevExpress...")
            await page.wait_for_selector('tr[class*="dxgvDataRow_"]', timeout=15000)
        except Exception:
            print("[CẢNH BÁO] DOM Timeout. Session Microsoft có thể đã bị invalid.")
            await browser.close()
            return [] # Trả về mảng rỗng để trigger luồng renew

        timetable_data = []

        # Parse DOM Node
        rows = await page.locator('tr[class*="dxgvDataRow_"]').all()
        print(f"[WORKER] Mount thành công {len(rows)} node dữ liệu. Tiến hành bóc tách...")

        for row in rows:
            cols = await row.locator('td').all_inner_texts()
            
            if len(cols) >= 13:
                ma_lop = cols[3].strip()
                ma_hp = cols[6].strip()

                if ma_lop and ma_hp:
                    course = {
                        "thoi_gian": cols[0].strip(),
                        "tuan_hoc": cols[1].strip(),
                        "phong_hoc": cols[2].strip(),
                        "ma_lop": ma_lop,
                        "loai_lop": cols[4].strip(),
                        "nhom": cols[5].strip(),
                        "ma_hp": ma_hp,
                        "ten_hp": cols[7].strip(),
                        "ghi_chu": cols[8].strip(),
                        "hinh_thuc": cols[9].strip(),
                        "giang_vien": cols[10].strip()
                    }
                    timetable_data.append(course)

        await browser.close()
        return timetable_data


async def main_scheduler():
    """Hàm điều phối luồng thực thi chính"""
    
    # 1. Boot check: File state chưa có thì ép tạo
    if not STATE_FILE.exists():
        print("[INIT] Missing state file. Kích hoạt renew_session()...")
        await renew_session()
        
        if not STATE_FILE.exists():
            print("[FATAL] Không thể khởi tạo session. Exiting...")
            return

    # 2. Thực thi worker
    data = await crawl_timetable()
    
    # 3. Fallback logic: Cào trượt do session chết
    if not data:
        print("[FALLBACK] Cache miss hoặc token expired. Refreshing state...")
        await renew_session()
        
        print("[FALLBACK] Retry payload injection...")
        data = await crawl_timetable()
        
        if not data:
            print("[FATAL] Retry failed. Check lại cấu trúc mạng hoặc DOM của server.")
            return

    # 4. Success Pipeline
    print(f"\n[SUCCESS] Parse hoàn tất {len(data)} object. Sẵn sàng pipe vào Database.")
    for item in data:
        print(item)

if __name__ == "__main__":
    asyncio.run(main_scheduler())