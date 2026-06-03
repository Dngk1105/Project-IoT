import asyncio
import hashlib
from dateutil.rrule import rrulestr
import unicodedata
from playwright.async_api import async_playwright
from pathlib import Path
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
import json
import aiofiles
from sqlalchemy import select

from core.logger import get_logger
from core.database import AsyncSessionLocal
from models.calendar import EventSource, CalendarEvent
from schemas.calendar import CalendarEventCreate
from crud.calendar import create_event, clear_future_events_by_source

logger = get_logger("hust_qldt_pipeline", log_file="hust_qldt_sync.log")

STATE_FILE = Path(__file__).parent / "hust_qldt_state.json"
TARGET_URL = "https://qldt.hust.edu.vn/students/learn/timetable"
API_KEYWORD = "query-student-timetable-in-range"
TZ = ZoneInfo("Asia/Ho_Chi_Minh")
ANCHOR_DATE = datetime(2026, 2, 23, tzinfo=TZ)
ANCHOR_WEEK = 25

# Bảng Map Kíp và Tiết
TIET_START_MAP = {  1: time(6, 45), 
                    2: time(7, 30), 
                    3: time(8, 25), 
                    4: time(9, 20), 
                    5: time(10, 15), 
                    6: time(11, 0), 
                    7: time(12, 30), 
                    8: time(13, 15), 
                    9: time(14, 10), 
                    10: time(15, 5), 
                    11: time(16, 0), 
                    12: time(16, 45)
                }
TIET_END_MAP =  {   1: time(7, 30), 
                    2: time(8, 15), 
                    3: time(9, 10), 
                    4: time(10, 5), 
                    5: time(11, 0), 
                    6: time(11, 45), 
                    7: time(13, 15), 
                    8: time(14, 0), 
                    9: time(14, 55), 
                    10: time(15, 50), 
                    11: time(16, 45), 
                    12: time(17, 30)
                }
KIP_MAP =   {"Kíp 1": 
                {
                    "start": time(6, 45), 
                    "end": time(9, 10)
                }, 
            "Kíp 2": 
                {   "start": time(9, 20), 
                    "end": time(11, 45)
                }, 
            "Kíp 3": 
                {   "start": time(12, 30), 
                    "end": time(14, 55)
                }, 
            "Kíp 4": 
                {   "start": time(15, 5), 
                    "end": time(17, 30)
                }, 
            "Kíp 5": 
                {   "start": time(17, 45), 
                    "end": time(20, 10)
                }
            }
DAY_RRULE_MAP = {2: "MO", 3: "TU", 4: "WE", 5: "TH", 6: "FR", 7: "SA", 8: "SU", 1: "SU"}


async def renew_sso_session():
    """Xin cap lai session neu mat"""
    logger.warning("Khoi tao luong dang nhap thu cong")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        
        await page.goto(TARGET_URL)
        try:
            logger.info("Dang cho nguoi dung dang nhap Microsoft SSO...")
            await page.wait_for_url("**/login.microsoftonline.com/**", timeout=120000)
            await page.wait_for_url("**/qldt.hust.edu.vn/**", timeout=300000)
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(5000)
            
            await context.storage_state(path=STATE_FILE)
            logger.info(f"Da luu phien dang nhap thanh cong vao {STATE_FILE.name}")
        except Exception as e:
            logger.error(f"Loi khi renew session: {str(e)}")
        finally:
            await browser.close()
        
        
async def fetch_raw_data():
    """Goi API lay du lieu tu qldt"""
    if not STATE_FILE.exists():
        await renew_sso_session()
        if not STATE_FILE.exists(): return None 
    
    logger.info("Bat dau cao API") 
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(storage_state=STATE_FILE)
        page = await context.new_page()
        
        try:
            async with page.expect_response(lambda response: API_KEYWORD in response.url) as response_info:
                await page.goto(TARGET_URL)

            api_response = await response_info.value
            if api_response.status != 200:
                logger.error(f"API tra ve ma loi {api_response.status}")
                return None
            
            raw_json = await api_response.json()
            logger.info("Lay thanh cong lich hoc tu Qldt")
            
            data = raw_json.get("data", raw_json) if isinstance(raw_json, dict) else raw_json
            try:
                file_name = "qldt_raw_json.json"
                async with aiofiles.open(file_name, "w", encoding="utf-8") as file:
                    await file.write(json.dumps(data, ensure_ascii=False, indent=4))
                logger.info(f"Da luu lich hoc vao file {file_name} thanh cong")  
            except Exception as e:
                logger.error(f"Khong the luu file JSON: {e}")
            
            return data
        except Exception as e:
            logger.error(f"Loi crip API ngam: {str(e)}")
            return None
        finally:
            await browser.close()

def _remove_accents(input_str: str) -> str:
    # xoa dau tieng viet de loc tu khoa chuan xac
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    return u"".join([c for c in nfkd_form if not unicodedata.combining(c)])

def _gen_hust_id(class_id: str, dt_obj: datetime, suffix: str = "") -> str:
    """Hàm tạo ID cố định và duy nhất cho từng tiết học HUST"""
    raw_str = f"{class_id}_{dt_obj.isoformat()}_{suffix}"
    hash_str = hashlib.md5(raw_str.encode()).hexdigest()[:16]
    return f"hust_{class_id}_{hash_str}"

def _decode_time_code(code_str: str):
    """Giải mã cấu trúc SIS: Ví dụ '514' -> (Thứ 5, Tiết 4)"""
    code = int(code_str)
    weekday = code // 100       # Ví dụ: 5
    ca_tiet = code % 100        # Ví dụ: 14
    ca = ca_tiet // 10          # Ca 1 (Sáng) hoặc Ca 2 (Chiều)
    tiet_trong_ca = ca_tiet % 10 
    real_tiet = (ca - 1) * 6 + tiet_trong_ca  # Quy đổi ra tiết chuẩn 1-12
    return weekday, real_tiet

async def parse_and_load(json_data: list):
    success_count = 0
    now = datetime.now(TZ)
    
    # loc hoc ky moi nhat de loai bo sach mon hoc tu cac nam truoc
    all_semesters = [str(item.get("semester")) for item in json_data if item.get("semester")]
    current_semester = max(all_semesters) if all_semesters else ""
    
    semester_anchors = {}
    for item in json_data:
        sem = item.get("semester")
        if not sem: continue
        for cal in (item.get("_calendars") or []):
            st_ms = cal.get("_startSemesterDate", 0)
            st_wk = cal.get("_startSemesterWeek", 0)
            if st_ms > 0 and st_wk > 0:
                semester_anchors[sem] = (st_ms, st_wk)
                break
                
    async with AsyncSessionLocal() as db:
        try:
            logger.info("Dang quet HUST QLDT de dong bo Delta...")
            
            stmt = select(CalendarEvent).where(CalendarEvent.source == EventSource.HUST_CTT)
            result = await db.execute(stmt)
            existing_events = {ev.id: ev for ev in result.scalars().all()}
            scraped_events = {}

            for item in json_data:
                sem = str(item.get("semester", ""))
                # bo qua neu khong phai hoc ky hien tai
                if sem != current_semester:
                    continue
                
                course_name = item.get("courseName", "Khong ten")
                norm_name = _remove_accents(course_name.lower())
                if any(kw in norm_name for kw in ["quoc phong", "duong loi"]):
                    logger.debug(f"Da bo qua mon blacklist: {course_name}")
                    continue
                
                class_id = item.get("classId", "Unknown")

                anchor_ms, anchor_wk = semester_anchors.get(sem, (0, 0))
                if anchor_ms == 0:
                    anchor_ms = datetime(2026, 2, 23, tzinfo=TZ).timestamp() * 1000
                    anchor_wk = 25
                anchor_date = datetime.fromtimestamp(anchor_ms / 1000.0, tz=TZ)

                teachers = item.get("_teachers") or []
                teacher_name = teachers[0]["fullName"] if teachers else "Chua phan cong"
                
                base_summary = f"[{class_id}] {course_name}"
                base_desc = f"Ma HP: {item.get('courseId')}\nGV: {teacher_name}\nLop: {item.get('notes', '')}"
                
                for exam in (item.get("_examInfo") or []):
                    exam_timestamp = exam.get("examDate", -1) / 1000.0
                    if exam_timestamp <= 0: continue
                    
                    exam_date = datetime.fromtimestamp(exam_timestamp, tz=TZ)
                    session_name = exam.get("session", "Kíp 1")
                    kip_times = KIP_MAP.get(session_name, KIP_MAP["Kíp 1"])
                    start_dt = datetime.combine(exam_date.date(), kip_times["start"], tzinfo=TZ)
                    end_dt = datetime.combine(exam_date.date(), kip_times["end"], tzinfo=TZ)
                    
                    event_id = _gen_hust_id(class_id, start_dt, "EXAM")
                    exam_place = exam.get("place", "Chua xep")
                    
                    if event_id in scraped_events: 
                        existing_evt = scraped_events[event_id]
                        if exam_place and exam_place not in existing_evt.location:
                            existing_evt.location += f", {exam_place}"
                        continue
                        
                    if event_id in existing_events:
                        evt = existing_events[event_id]
                        evt.is_cancelled = False
                        evt.summary = f"THI CUOI KY: {base_summary}"
                        evt.start_time = start_dt
                        evt.end_time = end_dt
                        evt.location = exam_place
                    else:
                        evt = CalendarEvent(id=event_id, summary=f"THI CUOI KY: {base_summary}", description=f"Kip thi: {session_name}\n{base_desc}", location=exam_place, start_time=start_dt, end_time=end_dt, source=EventSource.HUST_CTT, is_cancelled=False)
                        db.add(evt)
                    scraped_events[event_id] = evt
                    success_count += 1
                
                canceled_dates = set()
                for report in (item.get("_absentReport") or []):
                    absent_ms = report.get("absentDate", -1)
                    if absent_ms > 0:
                        dt_cancel = datetime.fromtimestamp(absent_ms / 1000.0, tz=TZ).date()
                        canceled_dates.add(dt_cancel)

                    replaced_ms = report.get("replacedDate", -1)
                    if replaced_ms > 0:
                        dt_makeup = datetime.fromtimestamp(replaced_ms / 1000.0, tz=TZ).date()
                        rep_from, rep_to = report.get("replacedFrom", 1), report.get("replacedTo", 4)
                        
                        start_dt = datetime.combine(dt_makeup, TIET_START_MAP.get(rep_from, time(6, 45)), tzinfo=TZ)
                        end_dt = datetime.combine(dt_makeup, TIET_END_MAP.get(rep_to, time(11, 45)), tzinfo=TZ)
                        event_id = _gen_hust_id(class_id, start_dt, "MAKEUP")
                        
                        if event_id in scraped_events: continue
                        if event_id in existing_events:
                            evt = existing_events[event_id]
                            evt.is_cancelled = False
                            evt.start_time = start_dt
                            evt.end_time = end_dt
                            evt.location = report.get("replacedPlace", "Chua xep")
                        else:
                            evt = CalendarEvent(id=event_id, summary=f"HOC BU: {base_summary}", description=f"Hoc bu cho {dt_cancel.strftime('%d/%m')}\n{base_desc}", location=report.get("replacedPlace", "Chua xep"), start_time=start_dt, end_time=end_dt, source=EventSource.HUST_CTT, is_cancelled=False)
                            db.add(evt)
                        scraped_events[event_id] = evt
                        success_count += 1
                
                calendar_info = item.get("calendarInfo", "").strip()
                
                if calendar_info:
                    blocks = calendar_info.strip(';').split(';')
                    for block in blocks:
                        if not block: continue
                        tokens = block.split(',')
                        if len(tokens) < 4: continue
                        
                        start_code, end_code = tokens[1], tokens[2]
                        room = tokens[-1]
                        week_tokens = tokens[3:-1]
                        
                        weeks = set()
                        for wt in week_tokens:
                            if '-' in wt:
                                s, e = map(int, wt.split('-'))
                                weeks.update(range(s, e + 1))
                            elif wt.isdigit():
                                weeks.add(int(wt))
                                
                        weekday, start_tiet = _decode_time_code(start_code)
                        _, end_tiet = _decode_time_code(end_code)
                        
                        for w in sorted(weeks):
                            class_date = anchor_date + timedelta(weeks=(w - anchor_wk), days=(weekday - 2))
                            if class_date.date() in canceled_dates: continue
                                
                            start_dt = datetime.combine(class_date.date(), TIET_START_MAP.get(start_tiet, time(6, 45)), tzinfo=TZ)
                            end_dt = datetime.combine(class_date.date(), TIET_END_MAP.get(end_tiet, time(11, 45)), tzinfo=TZ)
                            event_id = _gen_hust_id(class_id, start_dt, "REGULAR")
                            
                            if event_id in scraped_events: continue
                            if event_id in existing_events:
                                evt = existing_events[event_id]
                                evt.is_cancelled = False
                                evt.location = room
                            else:
                                evt = CalendarEvent(id=event_id, summary=base_summary, description=f"Tuan {w}\n{base_desc}", location=room, start_time=start_dt, end_time=end_dt, source=EventSource.HUST_CTT, is_cancelled=False)
                                db.add(evt)
                            scraped_events[event_id] = evt
                            success_count += 1
                else:
                    for cal in (item.get("_calendars") or []):
                        weeks = cal.get("weeks") or []
                        start_sem_ms = cal.get("_startSemesterDate", 0)
                        start_sem_wk = cal.get("_startSemesterWeek", 0)
                        
                        if start_sem_ms == 0: start_sem_ms = anchor_ms
                        if start_sem_wk == 0: start_sem_wk = anchor_wk
                            
                        if not weeks: continue

                        day = cal.get("day", 2)
                        t_from, t_to = cal.get("from", 1), cal.get("to", 4)
                        start_sem_date = datetime.fromtimestamp(start_sem_ms / 1000.0, tz=TZ).date()
                        day_offset = (day - 2) if day != 1 else 6 

                        for w in sorted(weeks):
                            class_date = start_sem_date + timedelta(days=(w - start_sem_wk) * 7 + day_offset)
                            if class_date in canceled_dates: continue
                            
                            start_dt = datetime.combine(class_date, TIET_START_MAP.get(t_from, time(6, 45)), tzinfo=TZ)
                            end_dt = datetime.combine(class_date, TIET_END_MAP.get(t_to, time(11, 45)), tzinfo=TZ)
                            event_id = _gen_hust_id(class_id, start_dt, "REGULAR")
                            
                            if event_id in scraped_events: continue
                            if event_id in existing_events:
                                evt = existing_events[event_id]
                                evt.is_cancelled = False
                                evt.location = cal.get("place", "Chua xep")
                            else:
                                evt = CalendarEvent(id=event_id, summary=base_summary, description=f"Tuan {w}\n{base_desc}", location=cal.get("place", "Chua xep"), start_time=start_dt, end_time=end_dt, source=EventSource.HUST_CTT, is_cancelled=False)
                                db.add(evt)
                            scraped_events[event_id] = evt
                            success_count += 1

            for ev_id, db_ev in existing_events.items():
                if ev_id not in scraped_events:
                    db_ev.is_cancelled = True

            await db.commit()
            logger.info(f"Hoan tat dong bo! Da nap/cap nhat {success_count} su kien vao Database.")    
        except Exception as e:
            await db.rollback()
            logger.error(f"Loi nghiem trong khi parse va luu DB: {str(e)}", exc_info=True)

async def run_sync_pipeline():
    logger.info("--- KICH HOAT PIPELINE DONG BO QLDT ---")
    
    raw_data = await fetch_raw_data()
    if raw_data:
        await parse_and_load(raw_data)
    else:
        logger.warning("Pipeline that bai do khong lay duoc du lieu tu QLDT.")
        
if __name__ == "__main__":
    from core.database import init_db
    async def test_run():
        await init_db()
        await run_sync_pipeline()
        
    asyncio.run(test_run())