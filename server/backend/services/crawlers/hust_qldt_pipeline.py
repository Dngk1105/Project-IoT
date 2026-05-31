import asyncio
from playwright.async_api import async_playwright
from pathlib import Path
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
import json
import aiofiles

from core.logger import get_logger
from core.database import AsyncSessionLocal
from models.calendar import EventSource
from schemas.calendar import CalendarEventCreate
from crud.calendar import create_event, clear_future_events_by_source

logger = get_logger("hust_qldt_pipeline", log_file="hust_qldt_sync.log")

STATE_FILE = Path(__file__).parent / "hust_qldt_state.json"
TARGET_URL = "https://qldt.hust.edu.vn/students/learn/timetable"
API_KEYWORD = "query-student-timetable-in-range"
TZ = ZoneInfo("Asia/Ho_Chi_Minh")

# Bảng Map Kíp và Tiết
TIET_START_MAP = {1: time(6, 45), 
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
TIET_END_MAP =  {1: time(7, 30), 
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
            
async def parse_and_load(json_data: str):
    success_count = 0
    async with AsyncSessionLocal() as db:
        try:
            #Xoa lich cu truoc khi nap lich moi
            logger.info("Dang don dep lich cu cua HUST de chuan bi ghi de...")
            await clear_future_events_by_source(db, EventSource.HUST_CTT)
            
            #parse du lieu
            for item in json_data:
                class_id = item.get("classId", "Unknown")
                course_name = item.get("courseName", "Khong ten")
                teachers = item.get("_teachers") or []
                teacher_name = teachers[0]["fullName"] if teachers else "Chua phan cong"
                
                base_summary = f"[{class_id}] {course_name}"
                base_desc = f"Ma HP: {item.get('courseId')}\nGV: {teacher_name}\nLop: {item.get('notes', '')}"
                
                #Lich thi
                for exam in (item.get("_examInfo") or []):
                    exam_timestamp = exam.get("examDate", -1) / 1000.0
                    if exam_timestamp <= 0: continue
                    
                    exam_date = datetime.fromtimestamp(exam_timestamp, tz=TZ)
                    session = exam.get("session", "Kíp 1")
                    kip_times = KIP_MAP.get(session, KIP_MAP["Kíp 1"])
                    
                    exam_event = CalendarEventCreate(
                        summary=f"THI CUOI KY: {base_summary}",
                        description=f"Kip thi: {session}\n{base_desc}",
                        location=exam.get("place", "Chua xep phong"),
                        start_time=datetime.combine(exam_date.date(), kip_times["start"], tzinfo=TZ),
                        end_time=datetime.combine(exam_date.date(), kip_times["end"], tzinfo=TZ),
                        is_recurring=False,
                        source=EventSource.HUST_CTT
                    )
                    await create_event(db, exam_event)
                    success_count += 1
                
                #Lich nghi & Hoc bu
                canceled_dates = set()
                for report in (item.get("_absentReport") or []):
                    absent_ms = report.get("absentDate", -1)
                    if absent_ms > 0:
                        dt_cancel = datetime.fromtimestamp(absent_ms / 1000.0, tz=TZ).date()
                        canceled_dates.add(dt_cancel)
                        logger.info(f"Phat hien lich nghi: {course_name} ngay {dt_cancel}")

                    replaced_ms = report.get("replacedDate", -1)
                    if replaced_ms > 0:
                        dt_makeup = datetime.fromtimestamp(replaced_ms / 1000.0, tz=TZ).date()
                        rep_from, rep_to = report.get("replacedFrom", 1), report.get("replacedTo", 4)
                        
                        makeup_event = CalendarEventCreate(
                            summary=f"HOC BU: {base_summary}",
                            description=f"Hoc bu cho ngay {dt_cancel.strftime('%d/%m')}\n{base_desc}",
                            location=report.get("replacedPlace", "Chua xep phong"),
                            start_time=datetime.combine(dt_makeup, TIET_START_MAP.get(rep_from, time(6, 45)), tzinfo=TZ),
                            end_time=datetime.combine(dt_makeup, TIET_END_MAP.get(rep_to, time(11, 45)), tzinfo=TZ),
                            is_recurring=False,
                            source=EventSource.HUST_CTT
                        )
                        await create_event(db, makeup_event)
                        success_count += 1
                
                #Lich dinh ki
                for cal in (item.get("_calendars") or []):
                    weeks = cal.get("weeks") or []
                    start_sem_ms = cal.get("_startSemesterDate", 0)
                    if not weeks or start_sem_ms == 0: continue

                    day = cal.get("day", 2)
                    t_from, t_to = cal.get("from", 1), cal.get("to", 4)
                    start_sem_date = datetime.fromtimestamp(start_sem_ms / 1000.0, tz=TZ).date()
                    day_offset = (day - 2) if day != 1 else 6 

                    valid_dates = []
                    for w in sorted(weeks):
                        class_date = start_sem_date + timedelta(days=(w - cal.get("_startSemesterWeek", 0)) * 7 + day_offset)
                        if class_date not in canceled_dates:
                            valid_dates.append((w, class_date))

                    if not valid_dates: continue

                    groups, curr_group = [], [valid_dates[0]]
                    for i in range(1, len(valid_dates)):
                        if valid_dates[i][0] == curr_group[-1][0] + 1: curr_group.append(valid_dates[i])
                        else: groups.append(curr_group); curr_group = [valid_dates[i]]
                    groups.append(curr_group)

                    for group in groups:
                        first_date = group[0][1]
                        rrule_str = f"FREQ=WEEKLY;COUNT={len(group)};BYDAY={DAY_RRULE_MAP.get(day, 'MO')}"
                        
                        event = CalendarEventCreate(
                            summary=base_summary,
                            description=f"Tuan {group[0][0]} den {group[-1][0]}\n{base_desc}",
                            location=cal.get("place", "Chua xep phong"),
                            start_time=datetime.combine(first_date, TIET_START_MAP.get(t_from, time(6, 45)), tzinfo=TZ),
                            end_time=datetime.combine(first_date, TIET_END_MAP.get(t_to, time(11, 45)), tzinfo=TZ),
                            is_recurring=True,
                            rrule=rrule_str,
                            source=EventSource.HUST_CTT
                        )
                        await create_event(db, event)
                        success_count += 1
            logger.info(f"Hoan tat dong bo! Da nap {success_count} su kien vao Database.")    
        except Exception as e:
            logger.error(f"Loi nghiem trong khi parse va luu DB: {str(e)}")
     
#API goi cao du lieu            
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