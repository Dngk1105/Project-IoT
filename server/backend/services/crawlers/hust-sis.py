from playwright.async_api import async_playwright
import asyncio
from pathlib import Path

STATE_FILE = Path(__file__).parent / "hust_state.json"

async def crawl_timetable():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(storage_state=STATE_FILE)
        page = await context.new_page()

        print("Đang truy cập trang thời khóa biểu...")
        await page.goto(
            "https://ctt-sis.hust.edu.vn/Students/Timetables.aspx",
            wait_until="networkidle"
        )

        try:
            print("Đang chờ bảng thời khóa biểu xuất hiện...")
            await page.wait_for_selector('tr[class*="dxgvDataRow_"]', timeout=30000)
        except Exception as e:
            print("Không tìm thấy bảng. Có thể session đã hết hạn, huynh cần chạy lại hàm renew_session().")
            await browser.close()
            return []

        timetable_data = []

        # Lấy tất cả các dòng dữ liệu trong bảng
        rows = await page.locator('tr[class*="dxgvDataRow_"]').all()
        print(f"Phát hiện {len(rows)} dòng dữ liệu môn học. Đang bóc tách...")

        for row in rows:
            # Lấy text của toàn bộ các thẻ <td> trong dòng đó
            cols = await row.locator('td').all_inner_texts()
            
            # Đảm bảo dòng này có đủ 13 cột như trong HTML huynh gửi
            if len(cols) >= 13:
                ma_lop = cols[3].strip()
                ma_hp = cols[6].strip()

                # Chỉ lấy những dòng có Mã lớp và Mã HP hợp lệ
                if ma_lop and ma_hp:
                    course = {
                        "thoi_gian": cols[0].strip(),     # VD: Thứ 3,6h45 - 9h10
                        "tuan_hoc": cols[1].strip(),      # VD: 25-32,34-42
                        "phong_hoc": cols[2].strip(),     # VD: D9-205
                        "ma_lop": ma_lop,                 # VD: 168503
                        "loai_lop": cols[4].strip(),      # VD: LT+BT
                        "nhom": cols[5].strip(),          # VD: Nhóm 1
                        "ma_hp": ma_hp,                   # VD: IT4060
                        "ten_hp": cols[7].strip(),        # VD: Lập trình mạng
                        "ghi_chu": cols[8].strip(),       # VD: Kỹ thuật máy tính-K68S
                        "hinh_thuc": cols[9].strip(),     # VD: Giảng dạy trực tiếp (Offline)
                        "giang_vien": cols[10].strip()    # VD: Lê Bá Vui
                    }
                    timetable_data.append(course)

        await browser.close()
        return timetable_data

if __name__ == "__main__":
    asyncio.run(crawl_timetable())